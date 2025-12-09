# Prefer native mysqlclient if installed; otherwise fall back to PyMySQL.
try:
    import MySQLdb  # mysqlclient
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pymysql = None
