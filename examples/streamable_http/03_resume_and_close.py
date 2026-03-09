from __future__ import annotations

from shared_demo import pretty_json, run_session_resume_demo


def main() -> None:
    print(pretty_json(run_session_resume_demo()))


if __name__ == "__main__":
    main()
