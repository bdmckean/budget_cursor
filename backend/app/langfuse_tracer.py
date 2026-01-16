"""
Langfuse tracing integration for budget_cursor.

This module provides utilities to trace LLM calls and other operations
for monitoring and debugging transaction categorization.
"""

import os
from typing import Optional, Dict, Any

from dataclasses import dataclass

try:
    from langfuse import Langfuse
    from langfuse.types import TraceContext

    LANGFUSE_AVAILABLE = True
except ImportError:
    Langfuse = Any  # type: ignore
    TraceContext = Any  # type: ignore
    LANGFUSE_AVAILABLE = False


@dataclass
class TraceHandle:
    """Lightweight wrapper for Langfuse trace context."""

    client: Any
    trace_context: TraceContext
    root_span: Optional[object] = None

    def end(self):
        """End the root span if it is still open."""
        if self.root_span:
            try:
                self.root_span.end()
            except Exception:
                pass
            finally:
                self.root_span = None


class LangfuseTracer:
    """Wrapper for Langfuse client with budget_cursor-specific configuration."""

    def __init__(self):
        """Initialize the Langfuse tracer with environment variables."""
        self.enabled = (
            LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY") is not None
        )
        self.client = None

        if self.enabled:
            try:
                debug_mode = os.getenv("LANGFUSE_DEBUG", "false").lower() == "true"
                self.client = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                    host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
                    debug=debug_mode,
                )
                print(
                    f"✓ Langfuse client initialized successfully with host: {os.getenv('LANGFUSE_HOST')}"
                )
                print(
                    f"  Available methods: {[m for m in dir(self.client) if not m.startswith('_')]}"
                )
            except Exception as e:
                print(f"Warning: Failed to initialize Langfuse: {e}")
                import traceback

                traceback.print_exc()
                self.enabled = False

    def is_enabled(self) -> bool:
        """Check if Langfuse tracing is enabled and available."""
        return self.enabled

    def create_trace(
        self,
        name: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Create a new trace for monitoring an operation.

        Args:
            name: Name of the operation (e.g., "suggest_category")
            user_id: Optional user ID for tracking
            metadata: Optional metadata dictionary

        Returns:
            Trace object or None if tracing is disabled
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Create a trace ID and context
            trace_id = self.client.create_trace_id()
            trace_context = TraceContext(trace_id=trace_id, user_id=user_id or "system")

            # Create a root span for the trace
            root_span = self.client.start_span(
                trace_context=trace_context,
                name=name,
                metadata=metadata or {},
            )
            print(f"✓ Created trace: {name} (ID: {trace_id})")
            return TraceHandle(
                client=self.client, trace_context=trace_context, root_span=root_span
            )
        except Exception as e:
            print(f"Warning: Failed to create trace: {e}")
            import traceback

            traceback.print_exc()
            return None

    def add_generation(
        self,
        trace,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an LLM generation (API call) to the trace.

        Args:
            trace: Trace object from create_trace()
            name: Name of the generation (e.g., "ollama_categorization")
            model: Model name (e.g., "llama3.1:8b")
            input_text: Input/prompt sent to the model
            output_text: Output/response from the model
            usage: Optional dict with "prompt_tokens" and "completion_tokens"
            metadata: Optional additional metadata
        """
        if not trace or not self.client:
            return

        try:
            # Add a generation to the trace
            generation = self.client.start_generation(
                trace_context=trace.trace_context,
                name=name,
                model=model,
                input=input_text,
                metadata=metadata or {},
            )
            # Update with output and usage, then end
            generation.update(output=output_text, usage_details=usage)
            generation.end()
            print(f"✓ Added generation: {name}")
        except Exception as e:
            print(f"Warning: Failed to add generation to trace: {e}")
            import traceback

            traceback.print_exc()

    def add_span(
        self,
        trace,
        name: str,
        input_text: Optional[str] = None,
        output_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a span (non-LLM operation) to the trace.

        Args:
            trace: Trace object from create_trace()
            name: Name of the span (e.g., "load_categories")
            input_text: Optional input data
            output_text: Optional output data
            metadata: Optional additional metadata
        """
        if not trace or not self.client:
            return

        try:
            # Add a span to the trace
            span = self.client.start_span(
                trace_context=trace.trace_context,
                name=name,
                input=input_text or "",
                metadata=metadata or {},
            )
            # Update with output, then end
            if output_text:
                span.update(output=output_text)
            span.end()
            print(f"✓ Added span: {name}")
        except Exception as e:
            print(f"Warning: Failed to add span to trace: {e}")
            import traceback

            traceback.print_exc()

    def end_trace(self, trace: Optional[TraceHandle]) -> None:
        """Finalize a trace by flushing to ensure all events are sent."""
        if not trace:
            return
        try:
            # End the root span if needed
            if trace.root_span and hasattr(trace.root_span, "update"):
                trace.root_span.update()
            # Flush to ensure all events are sent
            if self.client:
                self.client.flush()
                print(f"✓ Trace flushed")
        except Exception as e:
            print(f"Warning: Failed to end trace: {e}")
            import traceback

            traceback.print_exc()


# Global instance
_tracer = None


def get_tracer() -> LangfuseTracer:
    """Get or create the global Langfuse tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer()
    return _tracer


def initialize_tracing():
    """Initialize Langfuse tracing (call this at app startup)."""
    tracer = get_tracer()
    if tracer.is_enabled():
        print("✓ Langfuse tracing enabled")
    else:
        print("⚠ Langfuse tracing disabled (check .env configuration)")
