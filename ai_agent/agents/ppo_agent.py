import sys
from pathlib import Path

_ai_agent_dir = Path(__file__).resolve().parent.parent
_repo_root = _ai_agent_dir.parent
for _p in (str(_ai_agent_dir), str(_repo_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stable_baselines3 import PPO

try:
    from ai_agent.env.gati_env import GatiEnv
except ModuleNotFoundError:
    from env.gati_env import GatiEnv


def train_ppo(total_timesteps: int = 100_000, save_path: str = "models/ppo_gati") -> Path:
    environment = GatiEnv()
    model = PPO(
        "MlpPolicy",
        environment,
        verbose=1,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        policy_kwargs=dict(net_arch=[256, 256]),
    )
    model.learn(total_timesteps=total_timesteps)

    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_path)
    environment.close()
    return output_path


if __name__ == "__main__":
    train_ppo()
