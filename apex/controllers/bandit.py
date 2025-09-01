"""Epsilon-greedy contextual bandit for topology selection."""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class EpsilonGreedyBandit:
    """Epsilon-greedy contextual bandit with Sherman-Morrison updates.
    
    This bandit learns which topology (star, chain, flat) works best
    for different contexts (phase, tokens used, messages sent, etc).
    """
    
    def __init__(
        self,
        n_actions: int = 3,  # star, chain, flat
        n_features: int = 12,  # context features
        epsilon: float = 0.1,
        alpha: float = 1.0,  # regularization parameter
        seed: Optional[int] = None
    ):
        """Initialize the bandit.
        
        Args:
            n_actions: Number of possible actions (topologies)
            n_features: Number of context features
            epsilon: Exploration rate (0.1 = 10% exploration)
            alpha: Regularization parameter for ridge regression
            seed: Random seed for reproducibility
        """
        self.n_actions = n_actions
        self.n_features = n_features
        self.epsilon = epsilon
        self.alpha = alpha
        
        # Initialize random state
        self.rng = np.random.RandomState(seed)
        
        # Initialize weight matrices for each action
        # Using ridge regression: (X^T X + alpha*I)^{-1} X^T y
        # We maintain A_inv = (X^T X + alpha*I)^{-1} and b = X^T y
        self.A_inv = [np.eye(n_features) / alpha for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.theta = [np.zeros(n_features) for _ in range(n_actions)]  # weights
        
        # Track statistics
        self.n_pulls = [0] * n_actions
        self.total_reward = [0.0] * n_actions
        self.history = []
    
    def select_action(self, features: np.ndarray) -> int:
        """Select an action using epsilon-greedy strategy.
        
        Args:
            features: Context feature vector
            
        Returns:
            Selected action index
        """
        # Ensure features is the right shape
        if len(features) != self.n_features:
            raise ValueError(f"Expected {self.n_features} features, got {len(features)}")
        
        # Epsilon-greedy selection
        if self.rng.random() < self.epsilon:
            # Explore: random action
            action = self.rng.randint(self.n_actions)
        else:
            # Exploit: choose best action based on current weights
            expected_rewards = [np.dot(self.theta[a], features) for a in range(self.n_actions)]
            action = int(np.argmax(expected_rewards))
        
        return action
    
    def update(self, features: np.ndarray, action: int, reward: float):
        """Update bandit weights using Sherman-Morrison formula.
        
        This allows efficient online updates without matrix inversion.
        
        Args:
            features: Context feature vector
            action: Action that was taken
            reward: Observed reward
        """
        # Update statistics
        self.n_pulls[action] += 1
        self.total_reward[action] += reward
        
        # Sherman-Morrison update for A_inv
        # A_new = A_old + x*x^T
        # A_new_inv = A_old_inv - (A_old_inv * x * x^T * A_old_inv) / (1 + x^T * A_old_inv * x)
        x = features.reshape(-1, 1)
        A_inv_x = self.A_inv[action] @ x
        denominator = 1 + (x.T @ A_inv_x)[0, 0]
        self.A_inv[action] -= (A_inv_x @ A_inv_x.T) / denominator
        
        # Update b = X^T y
        self.b[action] += features * reward
        
        # Update weights: theta = A_inv * b
        self.theta[action] = self.A_inv[action] @ self.b[action]
        
        # Record history
        self.history.append({
            "features": features.tolist(),
            "action": action,
            "reward": reward,
            "timestamp": len(self.history)
        })
    
    def get_stats(self) -> Dict:
        """Get bandit statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        stats = {
            "n_pulls": self.n_pulls,
            "total_reward": self.total_reward,
            "avg_reward": [
                self.total_reward[a] / max(1, self.n_pulls[a]) 
                for a in range(self.n_actions)
            ],
            "epsilon": self.epsilon,
            "total_samples": len(self.history)
        }
        
        # Add action names for clarity
        action_names = ["star", "chain", "flat"]
        stats["action_performance"] = {
            action_names[i]: {
                "pulls": self.n_pulls[i],
                "total_reward": self.total_reward[i],
                "avg_reward": stats["avg_reward"][i]
            }
            for i in range(self.n_actions)
        }
        
        return stats
    
    def save(self, path: Path):
        """Save bandit state to file.
        
        Args:
            path: Path to save file
        """
        state = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "epsilon": self.epsilon,
            "alpha": self.alpha,
            "A_inv": [A.tolist() for A in self.A_inv],
            "b": [b.tolist() for b in self.b],
            "theta": [t.tolist() for t in self.theta],
            "n_pulls": self.n_pulls,
            "total_reward": self.total_reward,
            "history": self.history
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self, path: Path):
        """Load bandit state from file.
        
        Args:
            path: Path to load file
        """
        with open(path, 'r') as f:
            state = json.load(f)
        
        self.n_actions = state["n_actions"]
        self.n_features = state["n_features"]
        self.epsilon = state["epsilon"]
        self.alpha = state["alpha"]
        self.A_inv = [np.array(A) for A in state["A_inv"]]
        self.b = [np.array(b) for b in state["b"]]
        self.theta = [np.array(t) for t in state["theta"]]
        self.n_pulls = state["n_pulls"]
        self.total_reward = state["total_reward"]
        self.history = state["history"]
    
    def decay_epsilon(self, decay_rate: float = 0.99, min_epsilon: float = 0.01):
        """Decay exploration rate over time.
        
        Args:
            decay_rate: Multiplicative decay factor
            min_epsilon: Minimum exploration rate
        """
        self.epsilon = max(min_epsilon, self.epsilon * decay_rate)