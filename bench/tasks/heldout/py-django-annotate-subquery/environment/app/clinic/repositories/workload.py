from django.db import models
from django.db.models.functions import Coalesce

from clinic.models import Appointment, Doctor


def doctor_workload(clinic_id, as_of):
    """Return the clinic roster with approved session minutes and future open slots."""
    return (Doctor.objects.filter(clinic_id=clinic_id)
            .annotate(approved_minutes=Coalesce(models.Sum('sessions__minutes',
                      filter=models.Q(sessions__approved=True)), models.Value(0)),
                      open_appointments=models.Value(0, output_field=models.IntegerField()))
            .order_by('display_name', 'id'))


def appointment_overview(clinic_id):
    """Separate administration endpoint; preserve its grouped counts."""
    return list(Appointment.objects.filter(doctor__clinic_id=clinic_id).values('state')
                .annotate(total=models.Count('id')).order_by('state'))
