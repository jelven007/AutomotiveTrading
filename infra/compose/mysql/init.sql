CREATE DATABASE IF NOT EXISTS qt_identity;
CREATE DATABASE IF NOT EXISTS qt_market;
CREATE DATABASE IF NOT EXISTS qt_model_config;
CREATE DATABASE IF NOT EXISTS qt_strategy;
CREATE DATABASE IF NOT EXISTS qt_risk;
CREATE DATABASE IF NOT EXISTS qt_trading;
CREATE DATABASE IF NOT EXISTS qt_kms;
CREATE DATABASE IF NOT EXISTS qt_audit;
CREATE DATABASE IF NOT EXISTS qt_backtest;

GRANT ALL PRIVILEGES ON qt_identity.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_market.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_model_config.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_strategy.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_risk.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_trading.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_kms.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_audit.* TO 'qt_app'@'%';
GRANT ALL PRIVILEGES ON qt_backtest.* TO 'qt_app'@'%';

FLUSH PRIVILEGES;
