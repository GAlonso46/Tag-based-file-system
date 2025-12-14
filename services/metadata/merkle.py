"""
Merkle Tree Implementation for Anti-Entropy

Used for efficient reconciliation of metadata after network partitions.
Allows comparing large metadata sets by comparing only hash roots,
then drilling down to identify specific divergent entries.
"""

import hashlib
from typing import Dict, List, Optional, Tuple


class MerkleNode:
    """Node in a Merkle tree"""
    def __init__(self, hash_value: str, is_leaf: bool = False):
        self.hash = hash_value
        self.is_leaf = is_leaf
        self.left: Optional['MerkleNode'] = None
        self.right: Optional['MerkleNode'] = None
        self.key: Optional[str] = None  # For leaf nodes: the file_id


class MerkleTree:
    """
    Merkle Tree for metadata integrity and efficient comparison.
    
    Used for anti-entropy: quickly identify which files differ
    between two Metadata replicas after a network partition.
    """
    
    def __init__(self, metadata: Dict[str, dict]):
        """
        Build a Merkle tree from file metadata.
        
        Args:
            metadata: Dictionary mapping file_id -> file_data
        """
        self.root: Optional[MerkleNode] = None
        self.metadata = metadata
        self._build_tree()
    
    def _hash_file(self, file_id: str, file_data: dict) -> str:
        """
        Create a hash for a single file entry.
        Includes: file_id, filename, tags, owner, lamport_time, version_vector
        """
        # Create deterministic string representation
        components = [
            file_id,
            file_data.get('filename', ''),
            ','.join(sorted(file_data.get('tags', []))),
            file_data.get('owner', ''),
            str(file_data.get('lamport_time', 0)),
            str(sorted(file_data.get('version_vector', {}).items()))
        ]
        
        data = '|'.join(components).encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    def _hash_combine(self, left_hash: str, right_hash: str) -> str:
        """Combine two hashes into a parent hash"""
        combined = (left_hash + right_hash).encode('utf-8')
        return hashlib.sha256(combined).hexdigest()
    
    def _build_tree(self):
        """Build the Merkle tree from metadata"""
        if not self.metadata:
            # Empty tree
            self.root = MerkleNode(hashlib.sha256(b'').hexdigest())
            return
        
        # Sort file IDs for deterministic tree structure
        sorted_files = sorted(self.metadata.items())
        
        # Create leaf nodes
        leaves = []
        for file_id, file_data in sorted_files:
            leaf_hash = self._hash_file(file_id, file_data)
            leaf = MerkleNode(leaf_hash, is_leaf=True)
            leaf.key = file_id
            leaves.append(leaf)
        
        # Build tree bottom-up
        current_level = leaves
        while len(current_level) > 1:
            next_level = []
            
            # Process pairs
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                
                # Handle odd number of nodes: duplicate last node
                if i + 1 >= len(current_level):
                    right = left
                else:
                    right = current_level[i + 1]
                
                # Create parent node
                parent_hash = self._hash_combine(left.hash, right.hash)
                parent = MerkleNode(parent_hash)
                parent.left = left
                parent.right = right
                
                next_level.append(parent)
            
            current_level = next_level
        
        self.root = current_level[0] if current_level else None
    
    def get_root_hash(self) -> str:
        """Get the root hash of the tree"""
        return self.root.hash if self.root else ""
    
    def get_divergent_keys(self, other: 'MerkleTree') -> List[str]:
        """
        Compare with another Merkle tree and return file_ids that differ.
        
        This is the anti-entropy mechanism: instead of comparing all metadata,
        we only compare the subtrees where hashes differ.
        
        Args:
            other: Another MerkleTree to compare against
            
        Returns:
            List of file_ids that are different between the two trees
        """
        divergent = []
        
        def traverse(node1: Optional[MerkleNode], node2: Optional[MerkleNode]):
            # Both None: no difference
            if node1 is None and node2 is None:
                return
            
            # One is None: all keys in the other are divergent
            if node1 is None or node2 is None:
                node = node1 or node2
                collect_all_keys(node)
                return
            
            # Hashes match: no need to check subtree
            if node1.hash == node2.hash:
                return
            
            # Hashes differ
            if node1.is_leaf and node2.is_leaf:
                # Leaf level: this key is divergent
                if node1.key:
                    divergent.append(node1.key)
            else:
                # Internal node: recurse into children
                traverse(node1.left, node2.left)
                traverse(node1.right, node2.right)
        
        def collect_all_keys(node: Optional[MerkleNode]):
            """Collect all leaf keys from a subtree"""
            if node is None:
                return
            if node.is_leaf and node.key:
                divergent.append(node.key)
            else:
                collect_all_keys(node.left)
                collect_all_keys(node.right)
        
        traverse(self.root, other.root)
        return divergent
    
    def to_protobuf(self) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Convert tree to protobuf-compatible format.
        
        Returns:
            Tuple of (root_hash, list of (file_id, leaf_hash) pairs)
        """
        root_hash = self.get_root_hash()
        
        # Collect leaf hashes for verification
        leaf_hashes = []
        
        def collect_leaves(node: Optional[MerkleNode]):
            if node is None:
                return
            if node.is_leaf and node.key:
                leaf_hashes.append((node.key, node.hash))
            else:
                collect_leaves(node.left)
                collect_leaves(node.right)
        
        collect_leaves(self.root)
        
        return root_hash, leaf_hashes


def compare_trees(tree1: MerkleTree, tree2: MerkleTree) -> Dict[str, str]:
    """
    Compare two Merkle trees and return divergence information.
    
    Returns:
        Dictionary with:
        - 'divergent_count': number of files that differ
        - 'divergent_keys': list of file_ids that differ
    """
    if tree1.get_root_hash() == tree2.get_root_hash():
        return {
            'match': True,
            'divergent_count': 0,
            'divergent_keys': []
        }
    
    divergent_keys = tree1.get_divergent_keys(tree2)
    
    return {
        'match': False,
        'divergent_count': len(divergent_keys),
        'divergent_keys': divergent_keys
    }
