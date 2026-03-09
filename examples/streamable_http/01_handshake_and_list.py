from __future__ import annotations

from shared_demo import pretty_json, run_handshake_demo


def main() -> None:
    print(pretty_json(run_handshake_demo()))


if __name__ == "__main__":
    main()
