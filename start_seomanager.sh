nohup ./daphneserver.sh > daphne.log 2>&1 &
nohup ./startcelery.sh > celery.log 2>&1 &