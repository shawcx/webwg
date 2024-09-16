
--
-- WebWG
--

-- WebWG Servers
CREATE TABLE IF NOT EXISTS servers (
    "instance"      TEXT       UNIQUE NOT NULL,
    "type"          TEXT       NOT NULL,
    "pub"           TEXT       NOT NULL,
    "interface"     TEXT       NOT NULL,
    "host"          TEXT       NOT NULL,
    "port"          INTEGER    NOT NULL,
    "network"       TEXT       NOT NULL,
    "mtu"           INTEGER    NOT NULL
    );

-- WebWG Peers
CREATE TABLE IF NOT EXISTS peers (
    "peer"          TEXT       UNIQUE NOT NULL,
    "pub"           TEXT       NOT NULL,
    "address"       TEXT       NOT NULL,
    "remote"        TEXT       NOT NULL,
    "created"       INTEGER    NOT NULL,
    "instance"      TEXT       REFERENCES servers("instance") ON DELETE CASCADE
    );

-- WebWG Interface Users
CREATE TABLE IF NOT EXISTS users (
    "username"      TEXT        UNIQUE NOT NULL,
    "password"      TEXT        NOT NULL,
    "disabled"      BOOLEAN,
    "created"       INTEGER,
    "last"          INTEGER
    );
