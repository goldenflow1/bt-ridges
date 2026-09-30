# Clinic Roster

Scheduling staff view each doctor's approved session allocation beside the number of future open appointments. Clinic isolation, display order and the minutes annotation already exist; the open-appointment annotation is unfinished.

`clinic/api.py` validates the request, `clinic/services/rota.py` assembles the response, and `clinic/repositories/workload.py` builds the queryset. `clinic/repositories/calendar.py` supports the independent appointment calendar. Model definitions and configuration are separate. The development database is initialized by the deployment image's schema bootstrap.
