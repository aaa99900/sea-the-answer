"""Export the Incheon–Port Said round-trip demonstration as UTC daily records."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
import json
from pathlib import Path

from scripts.simulate_voyage import ROUTE_PATH, Leg, Waypoint, daily_row, schedule, write_export


PORT_SAID_ARRIVAL = datetime(2026, 11, 9, 12, tzinfo=UTC)
PORT_SAID_DEPARTURE = datetime(2026, 11, 10, 6, tzinfo=UTC)
OUTBOUND_DAYS = 27
RETURN_DAYS = 31
INCHEON_DEPARTURE = PORT_SAID_ARRIVAL - timedelta(days=OUTBOUND_DAYS)
INCHEON_ARRIVAL = PORT_SAID_DEPARTURE + timedelta(days=RETURN_DAYS)
SHIP_ID = "sim-inc-psd-roundtrip-2026-11-09"

TIMING_REFERENCES = [
    # IPA's North Africa Express announcement gives 27 days to Port Said.
    "https://eng.icpa.or.kr/article/view.do?articleKey=31994&boardKey=217&currentPageNo=1&menuKey=3996",
    # 29 days Port Said–Shanghai plus 2 days Shanghai–Incheon give a return benchmark.
    "https://www.cma-cgm.com/ebusiness/schedules/line-services/schedules/BEX2?Direction=Next&LastPageIndex=1",
    "https://www.pancon-acs.com/doc/426c15ae809fd15a6d7de8396d26bf444dbd4a30.pdf",
]


def retime(legs: list[Leg], days: int, start_hour: float, start_nm: float) -> list[Leg]:
    """Match the scenario duration by scaling cruising legs, retaining slow passages and waits."""
    target = days * 24
    cruising = sum(leg.end_hour - leg.start_hour for leg in legs if leg.status == "underway")
    other = legs[-1].end_hour - cruising
    scale = (target - other) / cruising
    result = []
    hour = start_hour
    for index, leg in enumerate(legs):
        duration = leg.end_hour - leg.start_hour
        if leg.status == "underway":
            duration *= scale
        end = start_hour + target if index == len(legs) - 1 else hour + duration
        result.append(replace(leg, start_hour=hour, end_hour=end, start_nm=start_nm + leg.start_nm,
                              speed_kn=leg.distance_nm / (end - hour)))
        hour = end
    return result


def reverse_route(points: list[Waypoint]) -> list[Waypoint]:
    result = []
    for index in range(len(points) - 1, 0, -1):
        # Status describes the outgoing segment, so take it from the other endpoint.
        status = points[index - 1].status
        if index == len(points) - 1:
            status = "departure"
        elif index <= 4:  # Dongbaek to the Incheon W-1 anchorage
            status = "approach"
        result.append(replace(points[index], status=status))
    return result + [replace(points[0], status="arrived")]


def build_round_trip() -> dict:
    route = json.loads(ROUTE_PATH.read_text(encoding="utf-8"))
    points = [Waypoint(**point) for point in route["waypoints"]]
    start_date = INCHEON_DEPARTURE.date()
    midnight = datetime.combine(start_date, time.min, UTC)

    def hour(at: datetime) -> float:
        return (at - midnight).total_seconds() / 3600

    outward = retime(schedule(points), OUTBOUND_DAYS, hour(INCHEON_DEPARTURE), 0)
    outward_nm = outward[-1].start_nm + outward[-1].distance_nm
    port = points[-1]
    berth = Leg(port, port, "berthed", hour(PORT_SAID_ARRIVAL), hour(PORT_SAID_DEPARTURE), outward_nm, 0, 0)
    homeward = retime(schedule(reverse_route(points)), RETURN_DAYS, hour(PORT_SAID_DEPARTURE), outward_nm)
    legs = [*outward, berth, *homeward]

    departure_date = PORT_SAID_DEPARTURE.date().isoformat()
    arrival_date = INCHEON_ARRIVAL.date().isoformat()
    milestones = {
        start_date.isoformat(): "12:00 UTC 인천항 출항",
        PORT_SAID_ARRIVAL.date().isoformat(): "12:00 UTC 포트사이드 입항, 정박",
        departure_date: "06:00 UTC 포트사이드 출항",
        arrival_date: "06:00 UTC 인천항 도착",
    }
    records = []
    for index in range((INCHEON_ARRIVAL.date() - start_date).days + 1):
        row = daily_row(legs, start_date, index, SHIP_ID)
        homeward_day = row["date"] >= departure_date
        row["voyage"] = "모의 귀항 PSD→INC" if homeward_day else "모의 출항 INC→PSD"
        if homeward_day:
            row["note"] = row["note"].replace("가상 운항", "가상 예상 운항", 1)
        if row["date"] == arrival_date:
            row["note"] = row["note"].replace("입항 완료", "입항 예정", 1)
        if row["date"] in milestones:
            row["note"] += f" · {milestones[row['date']]}"
        records.append(row)

    return {
        "ships": [{"id": SHIP_ID, "name": "가상 선박 해답 2호 · 왕복 시나리오", "type": "컨테이너선",
                   "dwt": 80000, "imo": "", "from": "인천항", "to": "포트사이드 경유 인천항", "sample": True}],
        "records": records,
        "simulation": {
            "sample": True, "date_basis": "UTC",
            "outbound": {"departure_at": INCHEON_DEPARTURE.isoformat(), "arrival_at": PORT_SAID_ARRIVAL.isoformat(),
                         "duration_days": OUTBOUND_DAYS, "record_count": OUTBOUND_DAYS + 1},
            "return": {"departure_at": PORT_SAID_DEPARTURE.isoformat(), "arrival_at": INCHEON_ARRIVAL.isoformat(),
                       "duration_days": RETURN_DAYS, "record_count": RETURN_DAYS + 1, "projected": True},
            "references": [*TIMING_REFERENCES, *route["references"]],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="export format")
    parser.add_argument("--output", type=Path, help="new UTF-8 export file (default: stdout)")
    args = parser.parse_args()
    try:
        write_export(build_round_trip(), args.format, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"simulate_round_trip: {exc}\n")


if __name__ == "__main__":
    main()
