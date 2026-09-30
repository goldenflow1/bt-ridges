from clinic.models import Appointment


def calendar(clinic_id, start, end):
    return list(Appointment.objects.filter(doctor__clinic_id=clinic_id, starts_at__gte=start,
                starts_at__lt=end).order_by('starts_at', 'id').values('id', 'doctor_id', 'state'))
