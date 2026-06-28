from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app import database, collector
import logging

# Configure logger
logger = logging.getLogger("stock_tracker_scheduler")
logging.basicConfig(level=logging.INFO)

scheduler = BackgroundScheduler()

def _add_schedule_job(time_str: str, schedule_id: int):
    """
    Parse 'HH:MM' time string and register cron job in scheduler.
    """
    try:
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        
        job_id = f"stock_job_{schedule_id}"
        
        # Add cron job to trigger daily at HH:MM
        scheduler.add_job(
            collector.generate_report_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            name=f"Stock report at {time_str}",
            replace_existing=True
        )
        logger.info(f"Registered schedule job: {job_id} at {time_str}")
    except Exception as e:
        logger.error(f"Failed to add schedule job for {time_str}: {e}")

def reload_jobs():
    """
    Clear all registered jobs and reload active ones from Database.
    Allows dynamic updates without restarting the backend process.
    """
    # 1. Remove all existing jobs
    scheduler.remove_all_jobs()
    logger.info("Cleared all existing scheduler jobs.")
    
    # 2. Query active schedules from DB
    schedules = database.get_schedules()
    active_count = 0
    for sched in schedules:
        if sched["is_active"] == 1:
            _add_schedule_job(sched["time_str"], sched["id"])
            active_count += 1
            
    logger.info(f"Reloaded scheduler. {active_count} active jobs registered.")

def start_scheduler():
    """
    Start the background scheduler and load initial jobs.
    """
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started.")
        reload_jobs()
    else:
        logger.info("Scheduler already running.")
        
def shutdown_scheduler():
    """
    Shutdown the scheduler gracefully.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler shutdown.")
