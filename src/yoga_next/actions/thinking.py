from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .base import ActionSpace


@dataclass
class ThoughtData:
    thought: str
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    is_revision: Optional[bool] = None
    revises_thought: Optional[int] = None
    branch_from_thought: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_thoughts: Optional[bool] = None


class ThinkingActionSpace(ActionSpace):
    """
    A tool for sequential thinking that helps break down complex problems.

    This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
    Each thought can build on, question, or revise previous insights as understanding deepens.
    """

    def __init__(self, action_space_name: str = "thinking"):
        super().__init__(action_space_name, env=None)
        self.thought_history: List[ThoughtData] = []
        self.branches: Dict[str, List[ThoughtData]] = {}

    async def _handle_sequential_thinking(
        self,
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
        is_revision: Optional[bool] = None,
        revises_thought: Optional[int] = None,
        branch_from_thought: Optional[int] = None,
        branch_id: Optional[str] = None,
        needs_more_thoughts: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """A detailed tool for dynamic and reflective problem-solving through thoughts.
        This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
        Each thought can build on, question, or revise previous insights as understanding deepens.

        When to use this tool:
        - Breaking down complex problems into steps
        - Planning and design with room for revision
        - Analysis that might need course correction
        - Problems where the full scope might not be clear initially
        - Problems that require a multi-step solution
        - Tasks that need to maintain context over multiple steps
        - Situations where irrelevant information needs to be filtered out

        Key features:
        - You can adjust total_thoughts up or down as you progress
        - You can question or revise previous thoughts
        - You can add more thoughts even after reaching what seemed like the end
        - You can express uncertainty and explore alternative approaches
        - Not every thought needs to build linearly - you can branch or backtrack
        - Generates a solution hypothesis
        - Verifies the hypothesis based on the Chain of Thought steps
        - Repeats the process until satisfied
        - Provides a correct answer

        :param thought: Your current thinking step, which can include regular analytical steps,
            revisions of previous thoughts, questions about previous decisions,
            realizations about needing more analysis, changes in approach,
            hypothesis generation, and hypothesis verification.
        :param thought_number: Current number in sequence (can go beyond initial total if needed).
        :param total_thoughts: Current estimate of thoughts needed (can be adjusted up/down).
        :param next_thought_needed: True if you need more thinking, even if at what seemed like the end.
        :param is_revision: A boolean indicating if this thought revises previous thinking.
        :param revises_thought: If is_revision is true, which thought number is being reconsidered.
        :param branch_from_thought: If branching, which thought number is the branching point.
        :param branch_id: Identifier for the current branch (if any).
        :param needs_more_thoughts: If reaching end but realizing more thoughts needed.
        """
        if thought_number < 1:
            return {
                "status": "error",
                "message": "thought_number must be a positive integer"
            }

        if total_thoughts < 1:
            return {
                "status": "error",
                "message": "total_thoughts must be a positive integer"
            }

        if thought_number > total_thoughts:
            total_thoughts = thought_number

        if is_revision and revises_thought is not None:
            if revises_thought < 1 or revises_thought > len(self.thought_history):
                return {
                    "status": "error",
                    "message": f"revises_thought index {revises_thought} is out of range for thought history of length {len(self.thought_history)}"
                }

        if branch_from_thought is not None:
            if branch_from_thought < 1 or branch_from_thought > len(self.thought_history):
                return {
                    "status": "error",
                    "message": f"branch_from_thought index {branch_from_thought} is out of range for thought history of length {len(self.thought_history)}"
                }

        thought_data = ThoughtData(
            thought=thought,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            next_thought_needed=next_thought_needed,
            is_revision=is_revision,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            needs_more_thoughts=needs_more_thoughts
        )

        if branch_id is not None and branch_from_thought is not None:
            if branch_id not in self.branches:
                self.branches[branch_id] = []
            self.branches[branch_id].append(thought_data)
        else:
            self.thought_history.append(thought_data)

        current_summary = f"{thought_number}/{total_thoughts}"
        if needs_more_thoughts:
            current_summary += " (more thoughts needed)"

        has_active_branches = len(self.branches) > 0

        advice_parts = []
        if next_thought_needed:
            advice_parts.append("Please continue with your next thought step.")
        if needs_more_thoughts:
            advice_parts.append("Consider adding more thoughts as the analysis requires deeper exploration.")
        if is_revision:
            advice_parts.append(f"You are revising thought #{revises_thought}. Make sure to explain the correction clearly.")
        if branch_id is not None:
            advice_parts.append(f"You are exploring a branch '{branch_id}'. Continue developing this direction.")

        advice = " ".join(advice_parts) if advice_parts else "Continue with your analysis or call done when finished."

        return {
            "status": "success",
            "current_thought_summary": current_summary,
            "thought_history_count": len(self.thought_history),
            "has_active_branches": has_active_branches,
            "active_branch_count": len(self.branches),
            "advice": advice,
            "thought_data": {
                "thought_number": thought_number,
                "total_thoughts": total_thoughts,
                "is_revision": is_revision,
                "branch_id": branch_id
            }
        }

    def _format_thought(self, thought_data: ThoughtData) -> str:
        """Format a thought for display with visual styling."""
        prefix = ""
        context = ""

        if thought_data.is_revision:
            prefix = "🔄 Revision"
            context = f" (revising thought {thought_data.revises_thought})"
        elif thought_data.branch_from_thought:
            prefix = "🌿 Branch"
            context = (
                f" (from thought {thought_data.branch_from_thought}, ID: {thought_data.branch_id})"
            )
        else:
            prefix = "💭 Thought"
            context = ""

        header = f"{prefix} {thought_data.thought_number}/{thought_data.total_thoughts}{context}"
        border_length = max(len(header), len(thought_data.thought)) + 4
        border = "─" * border_length

        return f"""
 ┌{border}┐
 │ {header.ljust(border_length - 2)} │
 ├{border}┤
 │ {thought_data.thought.ljust(border_length - 2)} │
 └{border}┘"""
