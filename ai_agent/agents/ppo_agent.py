import sys
from pathlib import Path

_ai_agent_dir = Path(__file__).resolve().parent.parent
_repo_root = _ai_agent_dir.parent
for _p in (str(_ai_agent_dir), str(_repo_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.vec_env import DummyVecEnv

try:
    from ai_agent.env.gati_env import GatiEnv
except ModuleNotFoundError:
    from env.gati_env import GatiEnv


DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


def _make_env():
    return GatiEnv()


def train_ppo(
    total_timesteps: int = 100_000,
    save_path: str = "models/ppo_gati",
    resume: bool = False,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 64,
    n_epochs: int = 10,
) -> Path:
    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint_dir = output_path.parent / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if resume and output_path.exists():
        print(f"Resuming from {output_path}")
        model = PPO.load(str(output_path), device="cpu")
        env = GatiEnv()
        model.set_env(env)
        model.verbose = 1
    else:
        env = GatiEnv()
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            policy_kwargs=dict(net_arch=[256, 256]),
            device="cpu",
        )

    checkpoint_callback = CheckpointCallback(
        save_freq=10_000,
        save_path=str(checkpoint_dir),
        name_prefix="ppo_gati",
    )

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=checkpoint_callback,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted. Saving model...")
    finally:
        model.save(str(output_path))
        print(f"Model saved to {output_path}")
        env.close()

    return output_path


if __name__ == "__main__":
    train_ppo()
