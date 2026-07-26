import sys
from pathlib import Path

_ai_agent_dir = Path(__file__).resolve().parent.parent
_repo_root = _ai_agent_dir.parent
for _p in (str(_ai_agent_dir), str(_repo_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neat

try:
    from ai_agent.env.gati_env import GatiEnv
except ModuleNotFoundError:
    from env.gati_env import GatiEnv


def train_neat(config_path: str | Path | None = None, generations: int = 20):
    if config_path is None:
        config_path = _ai_agent_dir / "config" / "neat_config.txt"
    config_path = str(config_path)

    config = neat.config.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path,
    )
    population = neat.Population(config)
    environment = GatiEnv()

    def evaluate_genomes(genomes, neat_config):
        for _, genome in genomes:
            genome.fitness = 0.0

    winner = population.run(evaluate_genomes, generations)
    environment.close()
    return winner


if __name__ == "__main__":
    train_neat()
