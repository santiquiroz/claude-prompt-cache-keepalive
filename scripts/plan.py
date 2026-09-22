import argparse

TTL_MINUTES = 60
SAFETY_MINUTES = 10


def rung_delays(hours, every, first):
    horizon = hours * 60
    delays, current = [], first
    while current <= horizon:
        delays.append(current)
        current += every
    return delays


def main():
    parser = argparse.ArgumentParser(description="Minutes from now at which each keepalive rung must fire.")
    parser.add_argument("--hours", type=float, required=True, help="how long the cache must survive")
    parser.add_argument("--every", type=float, default=40, help="minutes between rungs (must be <= 50)")
    parser.add_argument("--first", type=float, default=20, help="minutes until the first rung (less than the cache time left minus 10)")
    args = parser.parse_args()
    if args.every > TTL_MINUTES - SAFETY_MINUTES:
        parser.error(f"--every must be <= {TTL_MINUTES - SAFETY_MINUTES}: the TTL is exactly 60 min and a 60m20s gap already lost the cache")
    delays = rung_delays(args.hours, args.every, args.first)
    for index, minutes in enumerate(delays, start=1):
        print(f"{index}/{len(delays)} {minutes:g}")


if __name__ == "__main__":
    main()
