# Shared helpers for scripts/*.sh and host/*.sh - source it, do not run it.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="${MCC_ENV:-$REPO/config/config.env}"
if [ -f "$CONF" ]; then
  # shellcheck disable=SC1090
  . "$CONF"
else
  echo "missing $CONF - copy config/config.example.env to config/config.env and edit it" >&2
  exit 1
fi
: "${ADB:=adb}" "${ADB_ADDR:?set ADB_ADDR in config.env}"
: "${STATE_DIR:=$HOME/.local/state/mcc-ha}"
mkdir -p "$STATE_DIR"

adb_() { $ADB -s "$ADB_ADDR" "$@"; }
# run a command as root on the machine
su_() { adb_ shell "su -c '$1'"; }
adb_connect() { $ADB connect "$ADB_ADDR" >/dev/null 2>&1; [ "$(adb_ get-state 2>/dev/null)" = device ]; }

mqtt_args() {
  local a=(-h "$MQTT_HOST" -p "${MQTT_PORT:-1883}")
  [ -n "${MQTT_USER:-}" ] && a+=(-u "$MQTT_USER" -P "$MQTT_PASSWORD")
  printf '%s\n' "${a[@]}"
}
# mqtt_pub <topic> <payload> [extra args]  (retained)
mqtt_pub() {
  local t=$1 p=$2; shift 2
  mapfile -t A < <(mqtt_args)
  ${MOSQUITTO_PUB:-mosquitto_pub} "${A[@]}" -r -t "$t" -m "$p" "$@"
}
