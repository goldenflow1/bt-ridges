from django.db import models


class Doctor(models.Model):
    clinic_id = models.IntegerField()
    display_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'doctors'


class Session(models.Model):
    doctor = models.ForeignKey(Doctor, related_name='sessions', on_delete=models.CASCADE)
    minutes = models.IntegerField()
    approved = models.BooleanField(default=False)

    class Meta:
        db_table = 'sessions'


class Appointment(models.Model):
    doctor = models.ForeignKey(Doctor, related_name='appointments', on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    state = models.CharField(max_length=30)

    class Meta:
        db_table = 'appointments'
