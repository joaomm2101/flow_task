#!/bin/bash
# End-to-end smoke test against a running instance (plain http, COOKIE_SECURE=false).
#   scripts/smoke_test.sh [base_url]      default: http://127.0.0.1:8000
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
JAR="$(mktemp)"
USERNAME="smoke_$(date +%s)_$RANDOM"
PASSWORD="Smoke-test-pw1"
trap 'rm -f "$JAR"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
expect() { local want="$1"; shift; local got; got="$(status "$@")"; [ "$got" = "$want" ] || fail "expected $want, got $got for: $*"; echo "ok   $want  ${*: -1}"; }

echo "waiting for $BASE/ready ..."
for _ in $(seq 1 60); do
  [ "$(status "$BASE/ready" || true)" = "200" ] && break
  sleep 2
done
expect 200 "$BASE/ready"
expect 200 "$BASE/healthy"
expect 404 "$BASE/docs"
expect 404 "$BASE/openapi.json"

headers="$(curl -sI "$BASE/auth/login-page")"
for h in content-security-policy x-frame-options x-content-type-options x-request-id; do
  echo "$headers" | grep -qi "^$h:" || fail "missing response header $h"
done
echo "ok   security headers + request id"

user_json="{\"username\":\"$USERNAME\",\"email\":\"$USERNAME@example.com\",\"first_name\":\"Smoke\",\"last_name\":\"Test\",\"password\":\"$PASSWORD\",\"phone_number\":\"1234567890\"}"
expect 201 -X POST -H 'Content-Type: application/json' -d "$user_json" "$BASE/auth/"
expect 409 -X POST -H 'Content-Type: application/json' -d "$user_json" "$BASE/auth/"
expect 422 -X POST -H 'Content-Type: application/json' -d "${user_json/$PASSWORD/weak}" "$BASE/auth/"
expect 401 -d "username=$USERNAME&password=wrong-password-1" "$BASE/auth/token"

expect 200 -c "$JAR" -d "username=$USERNAME&password=$PASSWORD" "$BASE/auth/token"
grep -q "#HttpOnly_.*access_token" "$JAR" || fail "session cookie is not HttpOnly"
echo "ok   session cookie is HttpOnly"

expect 200 -b "$JAR" "$BASE/todos/todo-page"
expect 201 -b "$JAR" -X POST -H 'Content-Type: application/json' \
  -d '{"title":"Smoke todo","description":"created by the smoke test","priority":2,"complete":false}' "$BASE/todos/todo"
curl -s -b "$JAR" "$BASE/todos/todo-page" | grep -q "Smoke todo" || fail "created todo is not on the dashboard"
echo "ok   created todo shows on the dashboard"
expect 403 -b "$JAR" -X POST -H 'Origin: https://evil.example' -H 'Content-Type: application/json' \
  -d '{"title":"forged","description":"cross origin","priority":1,"complete":false}' "$BASE/todos/todo"
expect 401 "$BASE/todos/"
echo "smoke test passed"
