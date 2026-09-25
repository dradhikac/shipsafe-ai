"""Generate requirements/CareHub_v2_4_Requirements.pdf using fpdf2."""

from fpdf import FPDF
import os

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "requirements", "CareHub_v2_4_Requirements.pdf")


def generate():
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    W = pdf.epw  # effective page width after margins

    # Title block
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(W, 10, "CareHub Appointment Service", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(W, 8, "Release Requirements v2.4", align="C")
    pdf.ln(6)

    # Introduction
    intro = (
        "These are the active release requirements for the CareHub Appointment Service "
        "v2.4 release. ShipSafe AI will validate each requirement against the implementation."
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(W, 6, intro)
    pdf.ln(6)

    requirements = [
        (
            "R001",
            "Cancelled appointments must not generate reminder notifications.",
            [
                "When an appointment is cancelled, reminder requests must be rejected.",
                "The system must return an appropriate error response.",
                "No notification record may be persisted for a cancelled appointment.",
            ],
        ),
        (
            "R002",
            "Appointment API responses must include appointment_id, status, and eta_minutes.",
            [
                "POST /appointments response must include appointment_id, status, eta_minutes.",
                "GET /appointments/<id> response must include appointment_id, status, eta_minutes.",
                "POST /appointments/<id>/cancel response must include appointment_id, status, eta_minutes.",
            ],
        ),
        (
            "R003",
            "Appointment priority must be persisted through a versioned database migration.",
            [
                "The priority field must be stored in the appointments table.",
                "Accepted values: normal, high, emergency.",
                "A versioned migration file must exist that adds the priority column.",
                "Priority submitted at creation must be retrievable via GET /appointments/<id>.",
            ],
        ),
        (
            "R004",
            "User-controlled database search input must use parameterized queries.",
            [
                "Queries with user-supplied input must use parameterized placeholders (?).",
                "String concatenation into SQL text is prohibited.",
                "Applies to all routes and service functions that accept user input.",
            ],
        ),
        (
            "R005",
            "Regression tests must cover cancellation, API contract, and appointment priority.",
            [
                "Tests must verify cancelled appointments do not trigger reminders (R001).",
                "Tests must verify API responses include appointment_id, status, eta_minutes (R002).",
                "Tests must verify appointment priority is persisted and retrievable (R003).",
                "All regression tests must be present and must pass.",
            ],
        ),
    ]

    for req_id, title, criteria in requirements:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(W, 8, req_id)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(W, 6, title)
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        for item in criteria:
            pdf.multi_cell(W, 5, f"  - {item}")
        pdf.ln(5)

    pdf.output(OUTPUT)
    print(f"PDF written: {OUTPUT}")


if __name__ == "__main__":
    generate()
