import asyncio
import inspect
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """A simple, in-process event bus for decoupling components, with async support."""

    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_name: str, callback):
        logger.info(f"[EventBus] Subscribing '{getattr(callback, '__name__', 'lambda')}' to event '{event_name}'")
        self._subscribers[event_name].append(callback)

    def emit(self, event_name: str, *args, **kwargs):
        """
        Emits an event, calling all subscribed synchronous callbacks and launching
        asynchronous callbacks as fire-and-forget tasks.

        For critical async operations where you need to ensure completion or handle
        exceptions, use `emit_async`.
        """
        if event_name != "log_message_received": # Avoid spamming the log
             logger.info(f"[EventBus] Emitting event '{event_name}'")

        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        # Fire-and-forget for non-critical UI updates, etc.
                        task = asyncio.create_task(callback(*args, **kwargs))
                        # Add a callback to log exceptions from the task
                        task.add_done_callback(self._handle_task_result)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    import traceback
                    logger.error(f"[EventBus] Error in sync callback for event '{event_name}': {e}", exc_info=True)
                    traceback.print_exc()

    async def emit_async(self, event_name: str, *args, **kwargs):
        """
        Emits an event and awaits all asynchronous (coroutine) callbacks.
        This is for critical paths where the caller needs to wait for the event
        to be fully processed. Synchronous callbacks are still called normally.
        """
        if event_name != "log_message_received":
            logger.info(f"[EventBus] Emitting async event '{event_name}' and awaiting subscribers")

        if event_name not in self._subscribers:
            return

        async_tasks = []
        for callback in self._subscribers[event_name]:
            try:
                if inspect.iscoroutinefunction(callback):
                    async_tasks.append(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"[EventBus] Error in sync callback during async emit for event '{event_name}': {e}", exc_info=True)

        if async_tasks:
            results = await asyncio.gather(*async_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"[EventBus] An exception occurred in an async subscriber for event '{event_name}': {result}", exc_info=result)

    def _handle_task_result(self, task: asyncio.Task):
        """Callback to log exceptions from fire-and-forget tasks."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Task cancellation is expected, no need to log.
        except Exception as e:
            logger.error(f"[EventBus] Exception in fire-and-forget task: {e}", exc_info=e)