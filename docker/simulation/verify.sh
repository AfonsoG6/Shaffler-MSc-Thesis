RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

EXPECTED_BOOTSTRAPPED_COUNT=6
EXPECTED_TGEN_STREAMS=40

bootstrapped_count="$(grep -r --include="*.tor.*.stdout" "Bootstrapped 100" | wc -l)"
printf "Bootstrapped count: ${bootstrapped_count}/$EXPECTED_BOOTSTRAPPED_COUNT\n"

if [ "${bootstrapped_count}" != "$EXPECTED_BOOTSTRAPPED_COUNT" ]; then
    printf "Verification ${RED}failed${NC}: Not all tor processes bootstrapped :(\n"
    exit 1
fi

stream_count="$(grep -r --include="*.tgen.*.stdout" "stream-success" | wc -l)"
printf "Successful tgen stream count: ${stream_count}/$EXPECTED_TGEN_STREAMS\n"

if [ "${stream_count}" != "$EXPECTED_TGEN_STREAMS" ]; then
    printf "Verification ${RED}failed${NC}: Not all tgen streams were successful :(\n"
    exit 1
fi

printf "Verification ${GREEN}suceeded${NC}: Yay :)\n"
