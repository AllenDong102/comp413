from typing import List


class PatientData:
    name: str
    id: int

    def __init__(self, name, id):
        self.name = name
        self.id = id


class GetUserResponse:
    name: str
    id: int
    role: str
    patients: List[PatientData]

    def __init__(self, name, id, role, patients):
        self.name = name
        self.id = id
        self.role = role
        self.patients = patients
