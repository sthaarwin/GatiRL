import argparse
import sys
from pathlib import Path

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
    parser.add_argument("--resume", action="store_true", help="Resume training from last saved model")
    parser.add_argument("--model-path", type=str, default="models/ppo_gati", help="Path to save/load model")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--n-steps", type=int, default=2048, help="Steps per rollout")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size for PPO")
    parser.add_argument("--n-epochs", type=int, default=10, help="Epochs per update")
    args = parser.parse_args()

    if args.algorithm == "ppo":
        train_ppo(
            total_timesteps=args.timesteps,
            save_path=args.model_path,
            resume=args.resume,
            learning_rate=args.lr,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
        )
    else:
        train_neat(generations=args.generations)


if __name__ == "__main__":
    main()
