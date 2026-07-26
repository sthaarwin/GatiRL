import argparse
import sys
from pathlib import Path

# Support running directly from inside ai_agent directory or from project root
_ai_agent_dir = Path(__file__).resolve().parent
_repo_root = _ai_agent_dir.parent
for _p in (str(_ai_agent_dir), str(_repo_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from ai_agent.agents.neat_agent import train_neat
    from ai_agent.agents.ppo_agent import train_ppo
except ModuleNotFoundError:
    from agents.neat_agent import train_neat
    from agents.ppo_agent import train_ppo


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a GatiRL agent.")
    parser.add_argument("--algorithm", choices=("ppo", "neat"), default="ppo")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--generations", type=int, default=20)
    args = parser.parse_args()

    if args.algorithm == "ppo":
        train_ppo(total_timesteps=args.timesteps)
    else:
        train_neat(generations=args.generations)


if __name__ == "__main__":
    main()
