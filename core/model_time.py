from datetime import datetime, timedelta, timezone

def get_latest_model_run() -> tuple[str, str]:
    """Get the latest available model run date and hour.
    
    Returns:
        tuple[str, str]: (date in YYYYMMDD format, hour in HH format)
    """
    current_time = datetime.now(timezone.utc)
    current_hour = current_time.hour
    
    # Find most recent cycle (00/06/12/18Z)
    cycle_hour = (current_hour // 6) * 6
    cycle_date = current_time
    
    # Model data is typically available ~5-6 hours after cycle start
    hours_since_cycle = current_hour - cycle_hour
    if hours_since_cycle < 6:
        # Go back to previous cycle
        if cycle_hour == 0:
            cycle_date = current_time - timedelta(days=1)
            cycle_hour = 18
        else:
            cycle_hour -= 6
            
    return cycle_date.strftime("%Y%m%d"), f"{cycle_hour:02d}" 