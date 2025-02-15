from datetime import datetime, timedelta, timezone

def get_latest_model_run() -> tuple[str, str]:
    """Get the latest available model run based on current UTC time.
    Returns tuple of (run_hour, date) where run_hour is 00/06/12/18 and date is YYYYMMDD"""
    now = datetime.now(timezone.utc)
    current_hour = now.hour

    model_runs = [0, 6, 12, 18]
    
    latest_run = max((run for run in model_runs if current_hour >= run + 5), default=18)

    if latest_run == 18 and current_hour < model_runs[0] + 5:
        now = now - timedelta(days=1)
        
    return str(latest_run).zfill(2), now.strftime("%Y%m%d") 