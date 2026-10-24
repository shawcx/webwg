#!/bin/bash
#
# Retakes docs/screenshot.png from a live demo: a webwg server and four
# devices in private network namespaces with real WireGuard tunnels, and
# headless Chrome to sign in and capture the hub server's page. It needs no
# root, only unprivileged user namespaces.
#
# Needs wireguard-tools, iproute2, curl, Chrome or Chromium, Node 22 or
# later, and webwg built with make and installed in .venv.
#
#   docs/screenshot.sh [output.png]

set -eu

DOCS=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$DOCS")
OUT=$(realpath -m "${1:-$DOCS/screenshot.png}")

# run again as root of a user, network and mount namespace of our own
if [ -z "${WEBWG_DEMO:-}" ]; then
    PYTHON=${PYTHON:-$REPO/.venv/bin/python}
    CHROME=${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)}
    [ -n "$CHROME" ] || { echo 'Chrome or Chromium is needed, or set CHROME' >&2; exit 1; }
    exec unshare -rnm env WEBWG_DEMO=1 PYTHON="$PYTHON" CHROME="$CHROME" "$0" "$OUT"
fi

WORK=$(mktemp -d)

# stop everything started in the namespaces, Chrome forks a dozen processes
cleanup() {
    for ns in $(ip netns list | cut -d' ' -f1); do
        kill $(ip netns pids "$ns") 2>/dev/null || true
    done
    wait 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT
trap 'echo "screenshot.sh: failed at line $LINENO" >&2; tail -n 5 "$WORK/server.log" >&2 2>/dev/null' ERR

# vpn.example.com resolves to the server's documentation address everywhere
mount -t tmpfs tmpfs /run
mkdir -p /run/netns
echo '198.51.100.1 vpn.example.com' > "$WORK/hosts"
mount --bind "$WORK/hosts" /etc/hosts

# the server sits on a bridge, the devices come from 203.0.113.0/24
ip netns add srv
ip -n srv link set lo up
ip -n srv link add br0 type bridge
ip -n srv link set br0 up
ip -n srv addr add 198.51.100.1/24 dev br0
ip -n srv addr add 203.0.113.1/24 dev br0
n=0
for device in laptop:10 nas:11 desk:12 phone:24; do
    name=${device%:*}
    n=$((n + 1))
    ip netns add "$name"
    ip -n "$name" link set lo up
    ip -n srv link add "v$n" type veth peer name eth0 netns "$name"
    ip -n srv link set "v$n" master br0 up
    ip -n "$name" addr add "203.0.113.${device#*:}/24" dev eth0
    ip -n "$name" link set eth0 up
    ip -n "$name" route add 198.51.100.0/24 via 203.0.113.1
    mkdir "$WORK/$name"
done

srv() { ip netns exec srv "$@"; }

cd "$WORK"
srv "$PYTHON" -m webwg --dblogin-add-user admin demo > /dev/null 2>&1
srv "$PYTHON" -m webwg -a 0.0.0.0 -p 80 > "$WORK/server.log" 2>&1 &
for _ in $(seq 40); do srv curl -s -o /dev/null http://127.0.0.1/login && break; sleep 0.25; done
srv curl -s -c "$WORK/jar" -o /dev/null -d 'username=admin&password=demo' http://127.0.0.1/login/dblogin

api() { srv curl -sf -o /dev/null -b "$WORK/jar" -X PUT -d "$2" "http://127.0.0.1/data/$1"; }

join() {
    (cd "$WORK/$1" && ip netns exec "$1" python3 -I "$REPO/cliwg.py" http://vpn.example.com "$1" -i home > /dev/null)
}

api servers/home '{"type":"hub","instance":"home","interface":"wg0","host":"vpn.example.com","port":51820,"network":"10.8.0.1","mtu":1280}'
api servers/lab '{"type":"isolated","instance":"lab","interface":"wg1","host":"vpn.example.com","port":51821,"network":"10.9.0.1","mtu":1280}'

for name in laptop nas desk; do
    join "$name"
    api "pending/$name" '{}'
    ip netns exec "$name" wg-quick up "$WORK/$name/home-$name.conf" > /dev/null 2>&1
done
api peers/tablet '{"name":"tablet","instance":"home","address":"10.8.0.5"}'
join phone

# different amounts of traffic so the peers don't all look alike
ip netns exec nas    ping -q -f -c 20000 -s 1200 10.8.0.1 > /dev/null
ip netns exec laptop ping -q -f -c 3000  -s 1200 10.8.0.1 > /dev/null
ip netns exec desk   ping -q -c 3 10.8.0.1 > /dev/null

srv "$CHROME" --headless=new --no-sandbox --disable-gpu --no-first-run --hide-scrollbars \
    --user-data-dir="$WORK/chrome" --remote-debugging-port=9222 about:blank > "$WORK/chrome.log" 2>&1 &
for _ in $(seq 60); do srv curl -s -o /dev/null http://127.0.0.1:9222/json/version && break; sleep 0.25; done

srv node "$DOCS/screenshot.mjs" http://vpn.example.com "$OUT"
