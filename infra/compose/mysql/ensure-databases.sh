#!/usr/bin/env sh
set -eu

case "${MYSQL_USER}" in
  "" | *[!A-Za-z0-9_]*)
    echo "MYSQL_USER 只能包含字母、数字和下划线。" >&2
    exit 1
    ;;
esac

export MYSQL_PWD="${MYSQL_ROOT_PASSWORD}"

# init.sql 只在新数据卷执行；该脚本兼容已有数据卷。
mysql --protocol=tcp -h mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS qt_identity;
CREATE DATABASE IF NOT EXISTS qt_trading;
GRANT ALL PRIVILEGES ON qt_identity.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON qt_trading.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
