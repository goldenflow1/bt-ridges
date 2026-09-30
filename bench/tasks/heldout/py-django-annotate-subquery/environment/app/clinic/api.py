from clinic.services.rota import roster


def get_roster(clinic_id, as_of):
    if as_of.tzinfo is None:
        raise ValueError('as_of must include a time zone')
    return {'doctors':roster(clinic_id, as_of)}
