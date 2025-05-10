"""
Reinforcement Learning for Dynamic Routing Optimization

This module implements a reinforcement learning (RL) agent using Q-learning
to dynamically adjust routing parameters based on network conditions.

The agent learns optimal routing policies by maximizing a reward function
that balances throughput, latency, and packet loss.

State: Current throughput, latency, packet loss
Actions: Adjust MTU, enable/disable split tunneling, prioritize AWS IPs
Reward: R = w1 * T_eff - w2 * L_tunnel - w3 * P_loss
"""

import os
import logging
import json
import numpy as np
import tensorflow as tf
from tensorflow import keras
from typing import Dict, List, Tuple, Optional
import random
from datetime import datetime
from pathlib import Path

# Local imports
from models.network_optimization import NetworkParameters, NetworkMetrics

logger = logging.getLogger(__name__)

# Define state and action spaces
STATE_DIM = 3  # [throughput, latency, packet loss]
ACTION_DIM = 4  # [adjust MTU up, adjust MTU down, toggle split tunnel, prioritize AWS IPs]

class ExperienceBuffer:
    """
    Implements a replay buffer to store and sample experiences for training.
    """
    def __init__(self, max_size=1000):
        """
        Initialize the experience buffer.
        
        Args:
            max_size: Maximum number of experiences to store
        """
        self.buffer = []
        self.max_size = max_size
        
    def add(self, state, action, reward, next_state, done):
        """
        Add a new experience to the buffer.
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state observed
            done: Whether the episode is done
        """
        experience = (state, action, reward, next_state, done)
        if len(self.buffer) < self.max_size:
            self.buffer.append(experience)
        else:
            self.buffer.pop(0)
            self.buffer.append(experience)
            
    def sample(self, batch_size):
        """
        Sample a batch of experiences from the buffer.
        
        Args:
            batch_size: Number of experiences to sample
            
        Returns:
            Tuple of states, actions, rewards, next_states, dones
        """
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones = zip(*batch)
        return states, actions, rewards, next_states, dones
    
    def size(self):
        """Get the current size of the buffer."""
        return len(self.buffer)


class RoutingAgent:
    """
    Reinforcement Learning agent for optimizing routing decisions.
    
    Uses a Deep Q-Network (DQN) to learn the optimal policy for adjusting
    routing parameters based on network conditions.
    """
    def __init__(self, learning_rate=0.001, gamma=0.95, epsilon=1.0, epsilon_decay=0.995,
                 epsilon_min=0.1, batch_size=32, memory_size=1000, model_dir='./models/saved_rl'):
        """
        Initialize the routing agent.
        
        Args:
            learning_rate: Learning rate for the neural network
            gamma: Discount factor for future rewards
            epsilon: Exploration rate (probability of random action)
            epsilon_decay: Rate at which epsilon decreases
            epsilon_min: Minimum exploration rate
            batch_size: Batch size for training
            memory_size: Size of the experience replay buffer
            model_dir: Directory to save/load the model
        """
        self.state_dim = STATE_DIM
        self.action_dim = ACTION_DIM
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        self.memory = ExperienceBuffer(memory_size)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True, parents=True)
        self.model_path = self.model_dir / 'routing_agent_model'
        
        # Create or load Q-Network
        if os.path.exists(str(self.model_path)):
            self.model = self._load_model()
            logger.info(f"Loaded RL model from {self.model_path}")
            # Use lower epsilon for loaded models (less exploration)
            self.epsilon = max(0.2, self.epsilon_min)
        else:
            self.model = self._build_model()
            logger.info("Created new RL model")
            
        # Target network for stability
        self.target_model = self._build_model()
        self.update_target_model()
        
        # Training metrics
        self.loss_history = []
        self.reward_history = []
        self.q_value_history = []
        
        # Action definitions with descriptions
        self.actions = [
            {"id": 0, "name": "increase_mtu", "description": "Increase MTU by 40 bytes"},
            {"id": 1, "name": "decrease_mtu", "description": "Decrease MTU by 40 bytes"},
            {"id": 2, "name": "toggle_split_tunnel", "description": "Toggle between full and split tunnel mode"},
            {"id": 3, "name": "prioritize_aws", "description": "Toggle AWS IP prioritization"}
        ]
        
    def _build_model(self):
        """
        Build a neural network model for Q-learning.
        
        Returns:
            Compiled Keras model
        """
        model = keras.Sequential([
            keras.layers.Dense(64, activation='relu', input_dim=self.state_dim),
            keras.layers.Dense(64, activation='relu'),
            keras.layers.Dense(self.action_dim, activation='linear')
        ])
        
        model.compile(loss='mse', optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate))
        return model
    
    def _save_model(self):
        """Save the current model to disk."""
        self.model.save(str(self.model_path))
        
        # Save metadata (hyperparameters)
        metadata = {
            "creation_date": datetime.now().isoformat(),
            "epsilon": self.epsilon,
            "gamma": self.gamma,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "loss_history": self.loss_history[-100:] if self.loss_history else [],
            "reward_history": self.reward_history[-100:] if self.reward_history else []
        }
        
        with open(str(self.model_dir / 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info(f"Saved model to {self.model_path}")
        
    def _load_model(self):
        """
        Load a saved model from disk.
        
        Returns:
            Loaded Keras model
        """
        try:
            return keras.models.load_model(str(self.model_path))
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return self._build_model()
        
    def update_target_model(self):
        """Update the target model with weights from the current model."""
        self.target_model.set_weights(self.model.get_weights())
        
    def remember(self, state, action, reward, next_state, done):
        """
        Store experience in memory for replay.
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state observed
            done: Whether the episode is done
        """
        self.memory.add(state, action, reward, next_state, done)
        
    def choose_action(self, state, explore=True):
        """
        Choose an action based on the current state.
        
        Args:
            state: Current state vector [throughput, latency, packet_loss]
            explore: Whether to explore randomly (True) or exploit (False)
            
        Returns:
            Selected action index
        """
        # Normalize state for the neural network
        norm_state = self._normalize_state(state)
        
        # Epsilon-greedy action selection
        if explore and np.random.rand() < self.epsilon:
            # Random action (exploration)
            return random.randrange(self.action_dim)
        
        # Reshape state for model prediction
        state_tensor = np.reshape(norm_state, [1, self.state_dim])
        
        # Get Q-values for all actions
        q_values = self.model.predict(state_tensor, verbose=0)[0]
        self.q_value_history.append(np.max(q_values))
        
        # Return action with highest Q-value (exploitation)
        return np.argmax(q_values)
    
    def _normalize_state(self, state):
        """
        Normalize the state vector for the neural network.
        
        Args:
            state: Raw state vector [throughput (Mbps), latency (ms), packet_loss (%)]
            
        Returns:
            Normalized state vector
        """
        # Define expected ranges for each state dimension
        throughput_range = [0, 10]      # 0-10 Mbps
        latency_range = [0, 300]        # 0-300 ms
        packet_loss_range = [0, 10]     # 0-10 %
        
        # Extract state components
        throughput, latency, packet_loss = state
        
        # Normalize each component to [0, 1] range
        norm_throughput = min(max(throughput, throughput_range[0]), throughput_range[1]) / throughput_range[1]
        norm_latency = min(max(latency, latency_range[0]), latency_range[1]) / latency_range[1]
        norm_packet_loss = min(max(packet_loss, packet_loss_range[0]), packet_loss_range[1]) / packet_loss_range[1]
        
        return [norm_throughput, norm_latency, norm_packet_loss]
    
    def train(self, batch_size=None):
        """
        Train the model on a batch of experiences.
        
        Args:
            batch_size: Size of batch to train on (default: self.batch_size)
            
        Returns:
            Training loss
        """
        if batch_size is None:
            batch_size = self.batch_size
            
        # Skip training if buffer is too small
        if self.memory.size() < batch_size:
            return 0
        
        # Sample batch from memory
        states, actions, rewards, next_states, dones = self.memory.sample(batch_size)
        
        # Convert to numpy arrays
        states = np.array([self._normalize_state(s) for s in states])
        next_states = np.array([self._normalize_state(s) for s in next_states])
        rewards = np.array(rewards)
        actions = np.array(actions)
        dones = np.array(dones, dtype=np.bool_)
        
        # Get current Q-values
        current_q = self.model.predict(states, verbose=0)
        
        # Get next Q-values from target model
        next_q = self.target_model.predict(next_states, verbose=0)
        
        # Update target Q-values with reward and discounted future rewards
        for i in range(batch_size):
            if dones[i]:
                current_q[i, actions[i]] = rewards[i]
            else:
                current_q[i, actions[i]] = rewards[i] + self.gamma * np.max(next_q[i])
        
        # Train the model
        history = self.model.fit(states, current_q, epochs=1, verbose=0)
        loss = history.history['loss'][0]
        self.loss_history.append(loss)
        
        # Decay epsilon for less exploration over time
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return loss
    
    def calculate_reward(self, metrics: NetworkMetrics, prev_metrics: Optional[NetworkMetrics] = None) -> float:
        """
        Calculate the reward for the current network performance.
        
        Reward = w1 * T_eff - w2 * L_tunnel - w3 * P_loss
        
        Args:
            metrics: Current network metrics
            prev_metrics: Previous network metrics (for calculating improvement)
            
        Returns:
            Calculated reward value
        """
        # Weights for different metrics
        w1 = 0.5  # Throughput weight
        w2 = 0.3  # Latency weight
        w3 = 0.2  # Packet loss weight
        
        # Get current values from metrics
        throughput = metrics.effective_throughput * 1000  # Convert to Mbps
        latency = metrics.total_latency
        packet_loss = metrics.packet_loss * 100  # Convert to percentage
        
        # Calculate base reward
        # Throughput is good (positive reward), latency and packet loss are bad (negative reward)
        base_reward = (
            w1 * min(throughput / 1.5, 5.0) -  # Normalize to 1.5 Mbps baseline, cap at 5x
            w2 * min(latency / 100, 3.0) -     # Normalize to 100ms baseline, cap at 3x
            w3 * min(packet_loss / 1.0, 10.0)  # Normalize to 1% baseline, cap at 10x
        )
        
        # Add bonus for improvement if we have previous metrics
        if prev_metrics is not None:
            prev_throughput = prev_metrics.effective_throughput * 1000
            prev_latency = prev_metrics.total_latency
            prev_packet_loss = prev_metrics.packet_loss * 100
            
            # Calculate improvement percentages
            if prev_throughput > 0:
                throughput_improvement = (throughput - prev_throughput) / prev_throughput
            else:
                throughput_improvement = 0
                
            if prev_latency > 0:
                latency_improvement = (prev_latency - latency) / prev_latency
            else:
                latency_improvement = 0
                
            if prev_packet_loss > 0:
                packet_loss_improvement = (prev_packet_loss - packet_loss) / prev_packet_loss
            else:
                packet_loss_improvement = 0
            
            # Calculate improvement reward
            improvement_reward = (
                w1 * min(throughput_improvement, 1.0) +
                w2 * min(latency_improvement, 1.0) +
                w3 * min(packet_loss_improvement, 1.0)
            )
            
            # Add improvement bonus
            reward = base_reward + improvement_reward
        else:
            reward = base_reward
        
        # Add additional reward for good absolute performance
        if throughput > 1.0 and latency < 70 and packet_loss < 2.0:
            reward += 1.0  # Bonus for good overall performance
            
        # Penalize very poor performance
        if throughput < 0.1 or latency > 200 or packet_loss > 15.0:
            reward -= 2.0  # Penalty for poor performance
        
        # Track reward history
        self.reward_history.append(reward)
        
        return reward
    
    def apply_action(self, action_idx: int, current_params: Dict[str, any]) -> Dict[str, any]:
        """
        Apply the selected action to the current parameters.
        
        Args:
            action_idx: Index of the action to apply
            current_params: Current network parameters
            
        Returns:
            Updated parameters after applying the action
        """
        action = self.actions[action_idx]
        new_params = current_params.copy()
        
        logger.info(f"Applying RL action: {action['name']} - {action['description']}")
        
        if action["name"] == "increase_mtu":
            # Increase MTU by 40 bytes, up to maximum of 1500
            new_params["mtu"] = min(current_params["mtu"] + 40, 1500)
            
        elif action["name"] == "decrease_mtu":
            # Decrease MTU by 40 bytes, with minimum of 1280
            new_params["mtu"] = max(current_params["mtu"] - 40, 1280)
            
        elif action["name"] == "toggle_split_tunnel":
            # Toggle between full tunnel and split tunnel mode
            new_params["direct_tunnel"] = not current_params.get("direct_tunnel", True)
            
        elif action["name"] == "prioritize_aws":
            # Toggle AWS IP prioritization
            new_params["prioritize_aws"] = not current_params.get("prioritize_aws", False)
        
        return new_params
    
    def save(self):
        """Save the model and training history."""
        self._save_model()
        
    def get_diagnostic_info(self):
        """
        Get diagnostic information about the agent's state.
        
        Returns:
            Dict containing agent diagnostics
        """
        return {
            "epsilon": self.epsilon,
            "memory_size": self.memory.size(),
            "avg_q_value": sum(self.q_value_history[-100:]) / max(1, len(self.q_value_history[-100:])) if self.q_value_history else 0,
            "avg_reward": sum(self.reward_history[-100:]) / max(1, len(self.reward_history[-100:])) if self.reward_history else 0,
            "avg_loss": sum(self.loss_history[-100:]) / max(1, len(self.loss_history[-100:])) if self.loss_history else 0,
            "action_defs": self.actions
        }


def state_from_metrics(metrics: NetworkMetrics) -> List[float]:
    """
    Convert network metrics to state vector for the RL agent.
    
    Args:
        metrics: Network performance metrics
        
    Returns:
        State vector [throughput, latency, packet_loss]
    """
    throughput = metrics.effective_throughput * 1000  # Convert Gbps to Mbps
    latency = metrics.total_latency
    packet_loss = metrics.packet_loss * 100  # Convert to percentage
    
    return [throughput, latency, packet_loss]


def train_on_simulated_data(agent: RoutingAgent, episodes=100):
    """
    Train the RL agent on simulated network data.
    
    Args:
        agent: RoutingAgent instance
        episodes: Number of training episodes
        
    Returns:
        Trained agent
    """
    from models.network_optimization import NetworkOptimizer, NetworkParameters
    
    optimizer = NetworkOptimizer()
    
    # Define range of simulated network conditions
    congestion_levels = np.linspace(0.0, 0.9, 10)
    bandwidths = np.linspace(0.0005, 0.005, 10)  # 0.5 Mbps to 5 Mbps
    
    logger.info(f"Training RL agent on {episodes} simulated episodes")
    
    for episode in range(episodes):
        # Randomly select network conditions
        congestion = np.random.choice(congestion_levels)
        bandwidth = np.random.choice(bandwidths)
        
        # Create initial parameters
        params = NetworkParameters(
            b_local=bandwidth,
            b_ec2=1.0,
            l_propagation=20.0 + congestion * 100,  # 20-120ms
            mtu=1420,
            buffer_size=1000,
            packet_size=1400,
            congestion_level=congestion
        )
        
        # Calculate initial metrics
        metrics = optimizer.calculate_metrics(params)
        
        # Convert to state
        state = state_from_metrics(metrics)
        
        # Initial parameters as dict for action application
        param_dict = {
            "mtu": params.mtu,
            "direct_tunnel": True,
            "prioritize_aws": False
        }
        
        # Take 5 actions per episode
        for step in range(5):
            # Choose action
            action = agent.choose_action(state)
            
            # Apply action to parameters
            new_param_dict = agent.apply_action(action, param_dict)
            
            # Update network parameters
            new_params = NetworkParameters(
                b_local=params.b_local,
                b_ec2=params.b_ec2,
                l_propagation=params.l_propagation,
                mtu=new_param_dict["mtu"],
                buffer_size=params.buffer_size,
                packet_size=min(new_param_dict["mtu"] - 20, 1400),
                congestion_level=params.congestion_level
            )
            
            # Calculate new metrics
            new_metrics = optimizer.calculate_metrics(new_params)
            
            # Convert to next state
            next_state = state_from_metrics(new_metrics)
            
            # Calculate reward
            reward = agent.calculate_reward(new_metrics, metrics)
            
            # Store in replay buffer
            done = (step == 4)  # Last step in episode
            agent.remember(state, action, reward, next_state, done)
            
            # Train the agent
            loss = agent.train()
            
            # Move to next state
            state = next_state
            metrics = new_metrics
            params = new_params
            param_dict = new_param_dict
            
        # Update target network every episode
        if episode % 10 == 0:
            agent.update_target_model()
            
        # Log progress
        if episode % 10 == 0:
            diagnostics = agent.get_diagnostic_info()
            logger.info(f"Episode {episode}/{episodes}: epsilon={diagnostics['epsilon']:.3f}, "
                       f"avg_reward={diagnostics['avg_reward']:.3f}")
            
    # Save the trained model
    agent.save()
    
    return agent