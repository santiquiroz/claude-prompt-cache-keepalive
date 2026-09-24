import argparse
import math
import sys

TTL_MINUTES = 60
SAFETY_MINUTES = 10
MAX_GAP_MINUTES = TTL_MINUTES - SAFETY_MINUTES
MAX_WORTHWHILE_TICKS = 20


def rung_delays(hours, every, first):
    horizon = hours * 60
    delays, current = [], first
    while current <= horizon:
        delays.append(current)
        current += every
    return delays


def input_error(args):
    if not 0 < args.hours < math.inf:
        return "--hours must be a finite number > 0"
    if not args.every > 0:
        return "--every must be > 0"
    if args.every > MAX_GAP_MINUTES:
        return f"--every must be <= {MAX_GAP_MINUTES}: the TTL is exactly {TTL_MINUTES} min and a 60m20s gap already lost the cache"
    if not 0 < args.first <= MAX_GAP_MINUTES:
        return f"--first must be > 0 and <= {MAX_GAP_MINUTES}: a later first rung fires after the cache expired"
    return None


def too_many_ticks_warning(ticks):
    if ticks <= MAX_WORTHWHILE_TICKS:
        return None
    return f"warning: {ticks} ticks; more than {MAX_WORTHWHILE_TICKS} costs more than one cold reload, size --hours to the real absence"


def main():
    parser = argparse.ArgumentParser(description="Minutes from now at which each keepalive rung must fire.")
    parser.add_argument("--hours", type=float, required=True, help="how long the cache must survive")
    parser.add_argument("--every", type=float, default=40, help="minutes between rungs (must be <= 50)")
    parser.add_argument("--first", type=float, default=20, help="minutes until the first rung (> 0 and <= 50, less than the cache time left minus 10)")
    args = parser.parse_args()
    error = input_error(args)
    if error:
        parser.error(error)
    delays = rung_delays(args.hours, args.every, args.first)
    warning = too_many_ticks_warning(len(delays))
    if warning:
        print(warning, file=sys.stderr)
    for index, minutes in enumerate(delays, start=1):
        print(f"{index}/{len(delays)} {minutes:g}")


if __name__ == "__main__":
    main()
