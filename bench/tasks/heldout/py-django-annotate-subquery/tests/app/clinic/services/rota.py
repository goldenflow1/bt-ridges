from clinic.repositories.workload import doctor_workload


def roster(clinic_id, as_of):
    return [{'id':doctor.id, 'name':doctor.display_name, 'approved_minutes':doctor.approved_minutes,
             'open_appointments':doctor.open_appointments} for doctor in doctor_workload(clinic_id, as_of)]
