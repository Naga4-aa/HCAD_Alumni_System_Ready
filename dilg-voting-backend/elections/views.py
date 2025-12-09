# elections/views.py
from datetime import datetime

from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    AccessGate,
    Candidate,
    Election,
    Notification,
    Nomination,
    Position,
    Voter,
    Vote,
    ElectionReminder,
    generate_pin,
    POSITION_CHOICES,
)
from .serializers import (
    BallotSubmitSerializer,
    CandidateSerializer,
    ElectionSerializer,
    NominationCreateSerializer,
    NominationSerializer,
    PositionSerializer,
    VoterMeSerializer,
    VoterSerializer,
    VoteSerializer,
    AdminVoterCreateSerializer,
    ElectionReminderSerializer,
    NotificationSerializer,
)

User = get_user_model()

# -----------------------
# HELPERS
# -----------------------

def normalize_name(val: str) -> str:
    """
    Simple normalization to reduce accidental duplicates:
    - lowercase
    - strip leading/trailing whitespace
    - collapse internal whitespace
    """
    if not val:
        return ""
    return " ".join(val.strip().lower().split())


# =======================
#  HELPERS
# =======================

def get_active_election():
    return Election.objects.filter(is_active=True).order_by("-nomination_start").first()


def get_authenticated_voter(request):
    token = request.headers.get("X-Session-Token")
    if not token:
        return None
    try:
        return Voter.objects.get(session_token=token, is_active=True)
    except Voter.DoesNotExist:
        return None


def get_admin_from_request(request):
    token = request.headers.get("X-Admin-Token")
    if not token:
        return None
    try:
        data = signing.loads(
            token,
            salt=ADMIN_SALT,
            max_age=ADMIN_TOKEN_MAX_AGE_SECONDS,
        )
        user_id = data.get("user_id")
        if not user_id:
            return None
        return User.objects.get(id=user_id, is_staff=True)
    except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
        return None


def maybe_auto_publish(election: Election):
    """
    Auto-publish results when the configured results_at time has passed and
    auto_publish_results is enabled.
    """
    if not election or election.results_published:
        return election
    if not election.auto_publish_results or not election.results_at:
        return election
    now = timezone.now()
    results_at = election.results_at
    if timezone.is_naive(results_at):
        results_at = timezone.make_aware(results_at, timezone.get_current_timezone())
    if now >= results_at:
        election.results_published = True
        election.results_published_at = now
        election.save(update_fields=["results_published", "results_published_at"])
    return election


# Access gate helpers
ACCESS_GATE_NAME = getattr(settings, "ACCESS_GATE_NAME", "default")
DEFAULT_ACCESS_CODE = "demo-passcode"


def ensure_access_gates():
    """
    Make sure there's at least one gate. If none exists, create the default.
    """
    if not AccessGate.objects.exists():
        gate = AccessGate(name=ACCESS_GATE_NAME or "default")
        gate.set_passcode(DEFAULT_ACCESS_CODE)
        gate.save()


def list_access_gates():
    """
    Return all gates. If none exist, create the default one first.
    """
    ensure_access_gates()
    return list(AccessGate.objects.all())


# =======================
#  VOTER AUTH
# =======================


@api_view(["GET"])
@permission_classes([AllowAny])
def access_status(request):
    """
    Returns the current passcode versions so the frontend can invalidate old cookies
    when admins change the passcode. Supports multiple gates.
    """
    gates = list_access_gates()
    payload = [{"name": g.name, "version": g.version} for g in gates]
    return Response({"gates": payload})


@api_view(["POST"])
@permission_classes([AllowAny])
def access_check(request):
    """
    Validate a shared passcode stored on the server. Matches against any gate.
    """
    passcode = (request.data.get("passcode") or "").strip()
    if not passcode:
        return Response({"error": "Passcode is required"}, status=400)

    gates = list_access_gates()
    for gate in gates:
        if gate.check_passcode(passcode):
            return Response({"ok": True, "name": gate.name, "version": gate.version})

    return Response({"error": "Incorrect passcode"}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def voter_login(request):
    voter_id = request.data.get("voter_id")
    pin = request.data.get("pin")

    if not voter_id or not pin:
        return Response({"error": "voter_id and pin are required"}, status=400)

    try:
        voter = Voter.objects.get(voter_id=voter_id, is_active=True)
    except Voter.DoesNotExist:
        return Response({"error": "Invalid credentials"}, status=400)

    if not voter.check_pin(pin):
        return Response({"error": "Invalid credentials"}, status=400)

    voter.start_session()

    return Response(
        {
            "token": voter.session_token,
            "voter": VoterMeSerializer(voter).data,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def voter_quick_login(request):
    """
    Lightweight entry: create or reuse a voter using name + batch_year.
    We still require explicit consent to keep downstream flows intact.
    """
    raw_name = (request.data.get("name") or "").strip()
    raw_batch = request.data.get("batch_year")
    campus = (request.data.get("campus_chapter") or "").strip()
    consent = bool(request.data.get("privacy_consent"))

    if not raw_name:
        return Response({"error": "Full name is required"}, status=400)
    try:
        batch_year = int(raw_batch)
    except (TypeError, ValueError):
        return Response({"error": "Valid batch year is required"}, status=400)
    if not consent:
        return Response({"error": "Consent is required to continue"}, status=400)

    normalized = normalize_name(raw_name)

    # Try to find an existing voter with the same normalized name + batch to avoid duplicates
    candidate_voters = Voter.objects.filter(batch_year=batch_year).order_by("id")
    voter = None
    for v in candidate_voters:
        if normalize_name(v.name) == normalized:
            voter = v
            break

    if voter:
        voter.is_active = True
        voter.privacy_consent = True
        voter.save(update_fields=["is_active", "privacy_consent"])
        voter.start_session()
        Notification.objects.create(
            type="login",
            message=f"Voter '{voter.name}' batch {voter.batch_year} signed in via quick entry.",
            is_hidden=False,
            is_read=False,
        )
    else:
        voter = Voter.objects.create(
            name=raw_name.strip(),
            batch_year=batch_year,
            campus_chapter=campus,
            privacy_consent=True,
            is_active=True,
        )
        voter.start_session()
        Notification.objects.create(
            type="info",
            message=f"Quick login created voter '{voter.name}' batch {voter.batch_year} (ID {voter.voter_id}).",
            is_hidden=False,
            is_read=False,
        )

    return Response(
        {
            "token": voter.session_token,
            "voter": VoterMeSerializer(voter).data,
        }
    )


@api_view(["POST"])
def voter_logout(request):
    voter = get_authenticated_voter(request)
    if voter:
        voter.end_session()
    return Response({"message": "Logged out"})


@api_view(["GET"])
def voter_me(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"authenticated": False}, status=200)
    return Response({"authenticated": True, "voter": VoterMeSerializer(voter).data})


# =======================
#  PUBLIC DATA
# =======================

@api_view(["GET"])
@permission_classes([AllowAny])
def current_election(request):
    election = maybe_auto_publish(get_active_election())
    if not election:
        return Response({"has_election": False}, status=200)
    return Response({"has_election": True, "election": ElectionSerializer(election).data})


@api_view(["GET"])
@permission_classes([AllowAny])
def positions_list(request):
    election = get_active_election()
    if not election:
        return Response([], status=200)
    positions_qs = Position.objects.filter(election=election, is_active=True)
    if not positions_qs.exists():
        # Seed default positions if none exist for the active election
        for idx, (code, _label) in enumerate(POSITION_CHOICES):
            Position.objects.create(
                election=election,
                name=code,
                display_order=idx,
                seats=1,
                is_active=True,
            )
        positions_qs = Position.objects.filter(election=election, is_active=True)
    positions = positions_qs.order_by("display_order", "name")
    return Response(PositionSerializer(positions, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def candidates_list(request):
    election = get_active_election()
    if not election:
        return Response([], status=200)
    qs = Candidate.objects.filter(position__election=election, is_official=True).annotate(votes_count=Count("votes"))
    position_id = request.query_params.get("position")
    if position_id:
        qs = qs.filter(position_id=position_id)
    qs = qs.order_by("position__display_order", "full_name")
    data = CandidateSerializer(qs, many=True, context={"request": request}).data
    # Attach vote counts so voter list aligns with admin tally
    for idx, cand in enumerate(qs):
        data[idx]["votes"] = cand.votes_count
    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def published_results(request):
    """
    Public: return per-position vote totals for the active election
    only when results are officially published.
    """
    election = maybe_auto_publish(get_active_election())
    if not election:
        return Response({"published": False, "reason": "no_active_election"}, status=200)
    if not election.results_published:
        return Response({"published": False, "reason": "not_published"}, status=200)

    positions = Position.objects.filter(election=election, is_active=True).order_by(
        "display_order", "name"
    )
    results_payload = []
    for pos in positions:
        candidates = Candidate.objects.filter(position=pos, is_official=True).order_by("full_name")
        # compute votes per candidate
        cand_data = []
        max_votes = 0
        for cand in candidates:
            votes_count = Vote.objects.filter(position=pos, candidate=cand).count()
            max_votes = max(max_votes, votes_count)
            cand_data.append(
                {
                    "id": cand.id,
                    "full_name": cand.full_name,
                    "batch_year": cand.batch_year,
                    "campus_chapter": cand.campus_chapter,
                    "photo_url": request.build_absolute_uri(cand.photo.url) if cand.photo else None,
                    "votes": votes_count,
                }
            )
        # flag winners (ties allowed)
        for entry in cand_data:
            entry["winner"] = max_votes > 0 and entry["votes"] == max_votes

        results_payload.append(
            {
                "position_id": pos.id,
                "position": pos.get_name_display(),
                "candidates": cand_data,
            }
        )

    return Response(
        {
            "published": True,
            "published_at": election.results_published_at,
            "election": {
                "id": election.id,
                "name": election.name,
            },
            "positions": results_payload,
        }
    )

# =======================
#  NOMINATIONS
# =======================

@api_view(["POST"])
def nominate(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    if not voter.privacy_consent:
        return Response({"error": "Consent is required"}, status=400)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if not election.is_nomination_open():
        return Response({"error": "Nomination period is closed"}, status=400)

    ser = NominationCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    data = ser.validated_data
    try:
        position = Position.objects.get(
            id=data["position_id"], election=election, is_active=True
        )
    except Position.DoesNotExist:
        return Response({"error": "Invalid position"}, status=404)

    existing = Nomination.objects.filter(election=election, nominator=voter).first()
    if existing:
        if existing.status == "rejected":
            # Allow resubmission: update the existing record, reset status to pending
            existing.position = position
            existing.nominee_full_name = data["nominee_full_name"].strip()
            existing.nominee_batch_year = data["nominee_batch_year"]
            existing.nominee_campus_chapter = data.get("nominee_campus_chapter", "")
            existing.contact_email = data.get("contact_email", "")
            existing.contact_phone = data.get("contact_phone", "")
            existing.reason = data.get("reason", "")
            existing.nominee_photo = data.get("nominee_photo")
            existing.is_good_standing = data.get("is_good_standing", False)
            existing.status = "pending"
            existing.rejection_reason = ""
            existing.promoted = False
            existing.promoted_at = None
            existing.save()
            return Response(NominationSerializer(existing).data, status=200)
        return Response({"error": "You already submitted a nomination"}, status=400)

    nomination = Nomination.objects.create(
        election=election,
        position=position,
        nominator=voter,
        nominee_full_name=data["nominee_full_name"].strip(),
        nominee_batch_year=data["nominee_batch_year"],
        nominee_campus_chapter=data.get("nominee_campus_chapter", ""),
        contact_email=data.get("contact_email", ""),
        contact_phone=data.get("contact_phone", ""),
        reason=data.get("reason", ""),
        nominee_photo=data.get("nominee_photo"),
        is_good_standing=data.get("is_good_standing", False),
    )

    # Notify admins of incoming nomination (no voter attached so it stays in admin inbox)
    Notification.objects.create(
        type="nomination_submitted",
        message=(
            f"New nomination: {nomination.nominee_full_name} for {nomination.position.get_name_display()} "
            f"by {voter.name} (batch {voter.batch_year})"
        ),
    )

    return Response(NominationSerializer(nomination).data, status=201)


@api_view(["GET"])
def my_nomination(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    try:
        nomination = Nomination.objects.get(election=election, nominator=voter)
    except Nomination.DoesNotExist:
        return Response({}, status=200)

    return Response(NominationSerializer(nomination).data)


# =======================
#  BALLOT
# =======================

@api_view(["POST"])
def submit_ballot(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    if not voter.privacy_consent:
        return Response({"error": "Consent is required"}, status=400)

    if voter.has_voted:
        return Response({"error": "You already submitted your ballot"}, status=400)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if not election.is_voting_open():
        return Response({"error": "Voting period is closed"}, status=400)

    ser = BallotSubmitSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    votes_payload = ser.validated_data["votes"]

    active_positions = list(
        Position.objects.filter(election=election, is_active=True).order_by("id")
    )
    expected_ids = {str(p.id) for p in active_positions}

    # ensure one per position and complete ballot
    if set(map(str, votes_payload.keys())) != expected_ids:
        return Response({"error": "Submit one vote for each position."}, status=400)

    # Pre-validate all selections
    selections = []
    for position in active_positions:
        candidate_id = votes_payload.get(str(position.id)) or votes_payload.get(position.id)
        try:
            candidate = Candidate.objects.get(
                id=candidate_id, position=position, is_official=True
            )
        except Candidate.DoesNotExist:
            return Response(
                {
                    "error": f"Invalid candidate for position {position.get_name_display()}"
                },
                status=400,
            )
        selections.append((position, candidate))

    with transaction.atomic():
        for position, candidate in selections:
            if Vote.objects.filter(voter=voter, position=position).exists():
                return Response(
                    {"error": "You already voted for this position"}, status=400
                )
            Vote.objects.create(voter=voter, position=position, candidate=candidate)

        voter.has_voted = True
        voter.save(update_fields=["has_voted"])

    return Response({"message": "Ballot submitted"}, status=201)


@api_view(["GET"])
def my_votes(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    qs = Vote.objects.filter(voter=voter).select_related("position", "candidate")
    data = [
        {
            "position_id": v.position_id,
            "position": v.position.get_name_display(),
            "candidate_id": v.candidate_id,
            "candidate": v.candidate.full_name,
        }
        for v in qs
    ]
    return Response(data)


# =======================
#  ADMIN AUTH
# =======================

ADMIN_SALT = "admin-session"
ADMIN_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"error": "username and password are required"}, status=400)

    user = authenticate(username=username, password=password)
    if not user or not user.is_staff:
        return Response({"error": "Invalid admin credentials"}, status=400)

    token = signing.dumps({"user_id": user.id}, salt=ADMIN_SALT)

    return Response(
        {
            "token": token,
            "admin": {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
            },
        }
    )


@api_view(["POST"])
def admin_logout(request):
    return Response({"message": "Admin logged out"})


@api_view(["GET"])
def admin_me(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"authenticated": False}, status=200)
    return Response(
        {
            "authenticated": True,
            "admin": {
                "username": admin_user.username,
                "full_name": admin_user.get_full_name() or admin_user.username,
                "is_superuser": admin_user.is_superuser,
            },
        }
    )


# =======================
#  ADMIN DATA
# =======================

@api_view(["GET", "POST"])
def admin_voters(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    if request.method == "GET":
        voters = Voter.objects.all().order_by("name")
        return Response(VoterSerializer(voters, many=True).data)

    serializer = AdminVoterCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data
    # Force campus to the Digos City chapter for this deployment.
    data["campus_chapter"] = "Digos City"
    raw_pin = data.pop("pin", "").strip() or None
    if not raw_pin:
        raw_pin = generate_pin()

    voter = Voter(**data)
    voter.set_pin(raw_pin)
    voter.save()

    out = VoterSerializer(voter).data
    out["pin"] = raw_pin
    return Response(out, status=201)


@api_view(["GET"])
def admin_tally(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response([], status=200)

    data = []
    positions = Position.objects.filter(election=election, is_active=True).prefetch_related(
        "candidates"
    )

    for pos in positions:
        candidates_data = []
        for cand in pos.candidates.filter(is_official=True):
            votes_count = Vote.objects.filter(position=pos, candidate=cand).count()
            candidates_data.append(
                {
                    "candidate_id": cand.id,
                    "full_name": cand.full_name,
                    "batch_year": cand.batch_year,
                    "campus_chapter": cand.campus_chapter,
                    "photo_url": request.build_absolute_uri(cand.photo.url) if cand.photo else None,
                    "votes": votes_count,
                }
            )

        data.append(
            {
                "position_id": pos.id,
                "position": pos.get_name_display(),
                "candidates": candidates_data,
            }
        )

    return Response(data)


@api_view(["GET"])
def admin_stats(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    total_voters = Voter.objects.count()
    voted_count = Voter.objects.filter(has_voted=True).count()
    turnout_percent = round((voted_count / total_voters * 100), 2) if total_voters else 0.0

    return Response(
        {
            "total_voters": total_voters,
            "voted_count": voted_count,
            "turnout_percent": turnout_percent,
        }
    )


@api_view(["GET"])
def admin_nominations(request):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response([], status=200)

    qs = Nomination.objects.filter(election=election).select_related("position", "nominator")
    return Response(NominationSerializer(qs, many=True).data)


@api_view(["POST"])
def admin_promote_nomination(request, nomination_id):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    try:
        nomination = Nomination.objects.select_related("position").get(id=nomination_id)
    except Nomination.DoesNotExist:
        return Response({"error": "Nomination not found"}, status=404)

    with transaction.atomic():
        candidate, created = Candidate.objects.get_or_create(
            position=nomination.position,
            full_name=nomination.nominee_full_name,
            defaults={
                "batch_year": nomination.nominee_batch_year,
                "campus_chapter": nomination.nominee_campus_chapter,
                "contact_email": nomination.contact_email,
                "contact_phone": nomination.contact_phone,
                "bio": nomination.reason,
                "photo": nomination.nominee_photo,
                "source_nomination": nomination,
                "is_official": True,
            },
        )
        # If the candidate already exists without a photo, use the nominee photo to help admin.
        if (not created) and (not candidate.photo) and nomination.nominee_photo:
            candidate.photo = nomination.nominee_photo
            candidate.save(update_fields=["photo"])
        nomination.promoted = True
        nomination.promoted_at = timezone.now()
        nomination.status = "promoted"
        nomination.rejection_reason = ""
        nomination.save(update_fields=["promoted", "promoted_at", "status", "rejection_reason"])
        Notification.objects.create(
            type="nomination_promoted",
            message=f"Your nomination for {nomination.nominee_full_name} ({nomination.position.get_name_display()}) was promoted.",
            voter=nomination.nominator,
        )

    return Response({
        "candidate": CandidateSerializer(candidate, context={"request": request}).data,
        "created": created,
    })


@api_view(["POST", "DELETE"])
def admin_candidate_photo(request, candidate_id):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    try:
        candidate = Candidate.objects.get(id=candidate_id, is_official=True)
    except Candidate.DoesNotExist:
        return Response({"error": "Candidate not found"}, status=404)

    if request.method == "DELETE":
        candidate.photo = None
        candidate.save(update_fields=["photo"])
        return Response(CandidateSerializer(candidate, context={"request": request}).data)

    if "photo" not in request.FILES:
        return Response({"error": "No photo uploaded"}, status=400)

    candidate.photo = request.FILES["photo"]
    candidate.save(update_fields=["photo"])

    return Response(CandidateSerializer(candidate, context={"request": request}).data)


@api_view(["POST"])
def admin_reject_nomination(request, nomination_id):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    reason = (request.data.get("reason") or "").strip()
    if not reason:
        return Response({"error": "Rejection reason is required"}, status=400)

    try:
        nomination = Nomination.objects.select_related("position").get(id=nomination_id)
    except Nomination.DoesNotExist:
        return Response({"error": "Nomination not found"}, status=404)

    nomination.status = "rejected"
    nomination.rejection_reason = reason
    nomination.promoted = False
    nomination.promoted_at = None
    nomination.save(update_fields=["status", "rejection_reason", "promoted", "promoted_at"])

    # Notify via admin notifications feed so admins can track decisions
    Notification.objects.create(
        type="nomination_rejected",
        message=f"Nomination for {nomination.nominee_full_name} ({nomination.position.get_name_display()}) was rejected: {reason}",
    )
    # Notify the voter
    Notification.objects.create(
        type="nomination_rejected",
        message=f"Your nomination for {nomination.nominee_full_name} ({nomination.position.get_name_display()}) was rejected: {reason}",
        voter=nomination.nominator,
    )

    return Response(NominationSerializer(nomination).data)


@api_view(["DELETE"])
def admin_delete_nomination(request, nomination_id):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    try:
        nomination = Nomination.objects.get(id=nomination_id)
    except Nomination.DoesNotExist:
        return Response({"error": "Nomination not found"}, status=404)

    nomination.delete()
    return Response({"message": "Nomination deleted."}, status=200)


@api_view(["GET", "POST"])
def voter_notifications(request):
  """
  Voter-facing notifications for nomination decisions and other events.
  Supports:
  - GET: list unread/visible notifications (can include read when ?history=1)
  - POST: mark_all_read, dismiss, delete
  """
  voter = get_authenticated_voter(request)
  if not voter:
      return Response({"error": "Authentication required"}, status=401)

  if request.method == "GET":
      show_history = request.query_params.get("history") in ["1", "true", "yes"]
      qs = Notification.objects.filter(voter=voter)
      if not show_history:
          qs = qs.filter(is_hidden=False)
      qs = qs.order_by("-created_at", "-id")[:100]
      unread_count = Notification.objects.filter(voter=voter, is_read=False, is_hidden=False).count()
      return Response(
          {
              "items": NotificationSerializer(qs, many=True).data,
              "unread_count": unread_count,
          }
      )

  action = (request.data.get("action") or "").strip()
  ids = request.data.get("ids") or []
  base_qs = Notification.objects.filter(voter=voter)
  if action == "mark_all_read":
      base_qs.filter(is_read=False).update(is_read=True)
      return Response({"message": "Marked all as read"})
  if action == "mark_read":
      base_qs.filter(id__in=ids).update(is_read=True)
      return Response({"message": "Marked as read"})
  if action == "dismiss":
      base_qs.filter(id__in=ids).update(is_hidden=True, is_read=True)
      return Response({"message": "Dismissed"})
  if action == "delete":
      base_qs.filter(id__in=ids).delete()
      return Response({"message": "Deleted"})
  if action == "delete_all":
      base_qs.delete()
      return Response({"message": "All notifications deleted"})

  return Response({"error": "Invalid action"}, status=400)


@api_view(["GET", "POST"])
def admin_reminders(request):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if request.method == "GET":
        reminders = ElectionReminder.objects.filter(election=election)
        return Response(ElectionReminderSerializer(reminders, many=True).data)

    ser = ElectionReminderSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    reminder = ser.save(election=election)
    return Response(ElectionReminderSerializer(reminder).data, status=201)


@api_view(["GET", "PUT", "POST"])
def admin_active_election(request):
    """
    GET: return the active election with timelines
    POST: create a new election with timelines
    PUT: update nomination/voting windows and is_active
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    payload = request.data or {}

    def parse_dt(key):
        """
        Parse a datetime string. Return a tuple of (value, provided_flag) so we can
        distinguish between "not provided" and "explicitly cleared".
        """
        if key not in payload:
            return None, False
        val = payload.get(key)
        if not val:
            # Explicit clear
            return None, True
        try:
            dt = datetime.fromisoformat(val)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt, True
        except Exception:
            raise ValueError(f"Invalid datetime for {key}")

    def validate_windows():
        try:
            nomination_start, ns_provided = parse_dt("nomination_start")
            nomination_end, ne_provided = parse_dt("nomination_end")
            voting_start, vs_provided = parse_dt("voting_start")
            voting_end, ve_provided = parse_dt("voting_end")
            results_at, ra_provided = parse_dt("results_at")
        except ValueError as exc:
            return None, None, {"error": str(exc)}

        if nomination_start and nomination_end and nomination_end <= nomination_start:
            return None, None, {"error": "Nomination end must be after start"}
        if voting_start and voting_end and voting_end <= voting_start:
            return None, None, {"error": "Voting end must be after start"}
        if nomination_end and voting_start and voting_start <= nomination_end:
            return None, None, {"error": "Voting start must be after nomination end"}

        return (
            {
                "nomination_start": nomination_start,
                "nomination_end": nomination_end,
                "voting_start": voting_start,
                "voting_end": voting_end,
                "results_at": results_at,
            },
            {
                "nomination_start": ns_provided,
                "nomination_end": ne_provided,
                "voting_start": vs_provided,
                "voting_end": ve_provided,
                "results_at": ra_provided,
            },
            None,
        )

    if request.method == "POST":
        parsed, _provided, error = validate_windows()
        if error:
            return Response(error, status=400)

        # Require timelines on creation so the election is usable.
        required_fields = [
            parsed["nomination_start"],
            parsed["nomination_end"],
            parsed["voting_start"],
            parsed["voting_end"],
        ]
        if not all(required_fields):
            return Response({"error": "Provide nomination and voting windows to create an election"}, status=400)

        name = (payload.get("name") or "").strip() or f"HCAD Alumni Election {timezone.now().year}"
        description = payload.get("description", "").strip()
        is_active = bool(payload.get("is_active", True))
        mode = (payload.get("mode") or "timeline").strip() or "timeline"
        auto_publish_results = bool(payload.get("auto_publish_results", True))

        previous_election = Election.objects.order_by("-nomination_start", "-id").first()
        election = Election.objects.create(
            name=name,
            description=description,
            nomination_start=parsed["nomination_start"],
            nomination_end=parsed["nomination_end"],
            voting_start=parsed["voting_start"],
            voting_end=parsed["voting_end"],
            results_at=parsed["results_at"],
            is_active=is_active,
            auto_publish_results=auto_publish_results,
            mode=mode if mode in ("timeline", "demo") else "timeline",
        )

        # Auto-provision positions from the latest election, or fall back to defaults.
        positions_source = (
            previous_election if previous_election and previous_election.id != election.id else None
        )
        created_positions = 0
        if positions_source:
            for pos in Position.objects.filter(election=positions_source):
                Position.objects.create(
                    election=election,
                    name=pos.name,
                    is_active=pos.is_active,
                    seats=pos.seats,
                    display_order=pos.display_order,
                )
                created_positions += 1
        if not created_positions:
            for idx, (code, _label) in enumerate(POSITION_CHOICES):
                Position.objects.create(
                    election=election,
                    name=code,
                    display_order=idx,
                    seats=1,
                    is_active=True,
                )

        return Response(ElectionSerializer(election).data, status=201)

    election = maybe_auto_publish(get_active_election())
    if not election:
        # Fallback to the most recent election so the admin UI can still edit
        election = maybe_auto_publish(Election.objects.order_by("-nomination_start", "-id").first())
        if not election:
            return Response({"error": "No election configured"}, status=404)

    if request.method == "GET":
        return Response(ElectionSerializer(election).data)

    # PUT
    parsed, provided, error = validate_windows()
    if error:
        return Response(error, status=400)

    fields = {}
    if "name" in payload:
        name_val = (payload.get("name") or "").strip()
        if not name_val:
            return Response({"error": "Election name cannot be empty"}, status=400)
        fields["name"] = name_val
    if "description" in payload:
        # Allow clearing description
        fields["description"] = (payload.get("description") or "").strip()
    if "mode" in payload:
        mode_val = (payload.get("mode") or "").strip()
        if mode_val and mode_val not in ("timeline", "demo"):
            return Response({"error": "Invalid mode"}, status=400)
        if mode_val:
            fields["mode"] = mode_val
            if mode_val == "timeline":
                fields["demo_phase"] = None
    if provided.get("nomination_start"):
        fields["nomination_start"] = parsed["nomination_start"]
    if provided.get("nomination_end"):
        fields["nomination_end"] = parsed["nomination_end"]
    if provided.get("voting_start"):
        fields["voting_start"] = parsed["voting_start"]
    if provided.get("voting_end"):
        fields["voting_end"] = parsed["voting_end"]
    if provided.get("results_at"):
        fields["results_at"] = parsed["results_at"]
    if "is_active" in payload:
        fields["is_active"] = bool(payload.get("is_active"))
    if "auto_publish_results" in payload:
        fields["auto_publish_results"] = bool(payload.get("auto_publish_results"))

    # If nothing to update, just return current election data
    if not fields:
        return Response(ElectionSerializer(election).data)

    for k, v in fields.items():
        setattr(election, k, v)
    election.save(update_fields=list(fields.keys()))

    return Response(ElectionSerializer(election).data)


@api_view(["POST"])
def admin_publish_results(request):
    """
    Publish or unpublish official results for the active/latest election.
    Body: { "publish": true/false }
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election() or Election.objects.order_by("-nomination_start", "-id").first()
    if not election:
        return Response({"error": "No election found"}, status=404)

    publish_flag = bool(request.data.get("publish", True))
    if publish_flag:
        election.results_published = True
        election.results_published_at = timezone.now()
    else:
        election.results_published = False
        election.results_published_at = None
    election.save(update_fields=["results_published", "results_published_at"])

    return Response(ElectionSerializer(election).data)


@api_view(["POST"])
def admin_demo_phase(request):
    """
    Demo controls: open/close nomination or voting without manual date input.
    action: open_nomination, close_nomination, open_voting, close_voting, exit_demo
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    action = (request.data.get("action") or "").strip()
    election = get_active_election() or Election.objects.order_by("-nomination_start", "-id").first()
    if not election:
        return Response({"error": "No election found"}, status=404)

    now = timezone.now()
    election.mode = "demo"
    if action == "open_nomination":
        election.nomination_start = now - timezone.timedelta(minutes=1)
        election.nomination_end = now + timezone.timedelta(days=30)
        election.voting_start = None
        election.voting_end = None
        election.is_active = True
        election.demo_phase = "nomination"
    elif action == "close_nomination":
        election.nomination_start = election.nomination_start or (now - timezone.timedelta(days=1))
        election.nomination_end = now - timezone.timedelta(minutes=1)
        election.demo_phase = "between"
    elif action == "open_voting":
        election.nomination_start = election.nomination_start or (now - timezone.timedelta(days=2))
        election.nomination_end = election.nomination_end or (now - timezone.timedelta(hours=1))
        election.voting_start = now - timezone.timedelta(minutes=1)
        election.voting_end = now + timezone.timedelta(days=30)
        election.is_active = True
        election.demo_phase = "voting"
    elif action == "close_voting":
        election.voting_start = election.voting_start or (now - timezone.timedelta(days=1))
        election.voting_end = now - timezone.timedelta(minutes=1)
        election.demo_phase = "closed"
    elif action == "exit_demo":
        election.mode = "timeline"
        election.demo_phase = None
    else:
        return Response({"error": "Invalid action"}, status=400)

    election.save(
        update_fields=[
            "nomination_start",
            "nomination_end",
            "voting_start",
            "voting_end",
            "is_active",
            "mode",
            "demo_phase",
        ]
    )
    return Response(ElectionSerializer(election).data)


@api_view(["POST"])
def admin_reset_voters(request):
    """
    Reset has_voted/is_active/session_token for all voters.
    If reset_pins=true, generate new PINs.
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    reset_pins = bool(request.data.get("reset_pins"))

    voters = Voter.objects.all()
    count = 0
    output = []
    for v in voters:
        v.has_voted = False
        v.is_active = True
        v.session_token = None
        if reset_pins:
            new_pin = generate_pin()
            v.set_pin(new_pin)
            output.append({"voter_id": v.voter_id, "pin": new_pin})
        v.save()
        count += 1

    return Response(
        {
            "message": f"Reset {count} voters.",
            "reset_pins": reset_pins,
            "updated": output if reset_pins else [],
        }
    )


@api_view(["POST"])
def admin_reset_election(request):
    """
    Admin: reset votes and nominations for the active (or latest) election,
    and clear voter has_voted/session tokens. Does NOT delete candidates.
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election() or Election.objects.order_by("-nomination_start", "-id").first()
    if not election:
        return Response({"error": "No election found"}, status=404)

    positions = Position.objects.filter(election=election)
    votes_deleted, _ = Vote.objects.filter(position__in=positions).delete()
    nominations_deleted, _ = Nomination.objects.filter(election=election).delete()

    voters = Voter.objects.all()
    for v in voters:
        v.has_voted = False
        v.session_token = None
        v.is_active = True
        v.save(update_fields=["has_voted", "session_token", "is_active"])

    # Clear the election timeline and deactivate until new dates are set.
    election.nomination_start = None
    election.nomination_end = None
    election.voting_start = None
    election.voting_end = None
    election.results_at = None
    election.auto_publish_results = True
    election.results_published = False
    election.results_published_at = None
    election.is_active = False
    election.save(
        update_fields=[
            "nomination_start",
            "nomination_end",
            "voting_start",
            "voting_end",
            "results_at",
            "auto_publish_results",
            "results_published",
            "results_published_at",
            "is_active",
        ]
    )

    return Response(
        {
            "message": "Election data reset.",
            "election": election.id,
            "votes_deleted": votes_deleted,
            "nominations_deleted": nominations_deleted,
            "voters_reset": voters.count(),
        }
    )


# =======================
#  ADMIN NOTIFICATIONS
# =======================


@api_view(["GET", "POST"])
def admin_notifications(request):
    """
    Simple admin notifications inbox.
    - GET: ?history=1 to include hidden items; otherwise hides dismissed items.
    - POST actions: mark_all_read, dismiss (ids list), delete (ids list), delete_all
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    if request.method == "GET":
        show_history = request.query_params.get("history") in ["1", "true", "yes"]
        qs = Notification.objects.filter(voter__isnull=True)
        if not show_history:
            qs = qs.filter(is_hidden=False)
        qs = qs.order_by("-created_at", "-id")[:200]  # cap to avoid huge payloads
        unread_count = (
            Notification.objects.filter(voter__isnull=True, is_read=False, is_hidden=False).count()
        )
        return Response(
            {
                "items": NotificationSerializer(qs, many=True).data,
                "unread_count": unread_count,
            }
        )

    action = (request.data.get("action") or "").strip()
    ids = request.data.get("ids") or []
    if action == "mark_all_read":
        Notification.objects.filter(is_read=False).update(is_read=True)
        return Response({"message": "Marked all as read"})
    if action == "dismiss":
        Notification.objects.filter(id__in=ids).update(is_hidden=True, is_read=True)
        return Response({"message": "Dismissed"})
    if action == "delete":
        Notification.objects.filter(id__in=ids).delete()
        return Response({"message": "Deleted"})
    if action == "delete_all":
        Notification.objects.all().delete()
        return Response({"message": "All notifications deleted"})

    return Response({"error": "Invalid action"}, status=400)
