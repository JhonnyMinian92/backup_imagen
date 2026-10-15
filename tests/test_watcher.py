import pytest

from backup_imagen.watcher import watch_for_usb


@pytest.mark.parametrize("poll_interval", [0, -1])
def test_watcher_rejects_nonpositive_poll_interval(poll_interval: float) -> None:
    with pytest.raises(ValueError, match="mayor que cero"):
        watch_for_usb(poll_interval)


@pytest.mark.parametrize("poll_interval", [float("nan"), float("inf")])
def test_watcher_rejects_nonfinite_poll_interval(poll_interval: float) -> None:
    with pytest.raises(ValueError, match="número finito"):
        watch_for_usb(poll_interval)
