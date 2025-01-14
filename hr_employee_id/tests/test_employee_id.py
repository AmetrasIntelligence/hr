# Copyright 2015 Salton Massally <smassally@idtlabs.sl>
# Copyright 2016 OpenSynergy Indonesia
# Copyright 2018 Brainbean Apps (https://brainbeanapps.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import common


class TestEmployeeID(common.TransactionCase):
    def setUp(self):
        super(TestEmployeeID, self).setUp()
        self.employee_model = self.env["hr.employee"]
        self.company = self.env.ref("base.main_company")
        self.sequence = self.env.ref("hr_employee_id.seq_hr_employee_id")

    def test_random_id_generation(self):
        # test ID generation for random
        employee = self.employee_model.create({"name": "Employee"})

        self.assertAlmostEqual(len(employee.identification_id), 5)

    def test_random_id_generation_changed_digits(self):
        # test ID generation for random but with defaults changed
        self.company.write({"employee_id_random_digits": 10})
        employee = self.employee_model.create({"name": "Employee"})

        self.assertAlmostEqual(len(employee.identification_id), 10)

    def test_sequences_id_generation(self):
        # test ID generation for a provided sequence
        self.company.write(
            {
                "employee_id_gen_method": "sequence",
                "employee_id_sequence": self.sequence.id,
            }
        )
        employee = self.employee_model.create({"name": "Employee"})

        self.assertTrue(len(employee.identification_id))

    def test_no_sequences_id_generation(self):
        # test ID generation for a provided sequence
        self.company.write({"employee_id_gen_method": "sequence"})
        employee = self.employee_model.create({"name": "Employee"})

        self.assertEqual(employee.identification_id, False)

    def test_custom_id(self):
        # if we pass the ID no generation occurs.
        # Let's set a sequence and check that is not used at all
        self.company.write(
            {
                "employee_id_gen_method": "sequence",
                "employee_id_sequence": self.sequence.id,
            }
        )
        number = self.sequence.number_next
        employee = self.employee_model.create(
            {"name": "Employee", "identification_id": "THERE_YOU_GO"}
        )
        self.assertEqual(employee.identification_id, "THERE_YOU_GO")
        self.assertEqual(self.sequence.number_next, number)

    def test_configuration_default_values(self):
        # test loading of default configuration values
        self.company.write(
            self.company.default_get(
                [
                    "employee_id_gen_method",
                    "employee_id_random_digits",
                    "employee_id_sequence",
                ]
            )
        )
        config_model = self.env["res.config.settings"]
        config = config_model.create({})
        self.assertTrue(config.company_id.id == self.company.id)
        self.assertTrue(config.employee_id_gen_method == "random")
        self.assertTrue(config.employee_id_random_digits == 5)
        self.assertFalse(config.employee_id_sequence is False)

    def test_configuration_set_default_values(self):
        """test loading of default values when the company fields are empty"""

        company = self.env.company
        company.employee_id_gen_method = False
        company.employee_id_random_digits = False

        config_model = self.env["res.config.settings"]
        config = config_model.create({})

        self.assertEqual(config.employee_id_gen_method, "random")
        self.assertEqual(config.employee_id_random_digits, 5)

    def test_multi_company_res_config(self):
        """Test different values for different companies."""

        DIGITS2 = 12
        METHOD2 = "sequence"

        Settings = self.env["res.config.settings"]
        company = self.env.company
        fields = list(Settings.fields_get())

        # Settings for first company
        vals1 = self.company.default_get(
            [
                "employee_id_gen_method",
                "employee_id_random_digits",
                "employee_id_sequence",
            ]
        )
        vals1.update({"employee_id_random_digits": 6})
        Settings.create(vals1).execute()

        # Set company 2 as main company
        company2 = self.env["res.company"].create({"name": "oobO"})
        self.env.user.write(
            {"company_ids": [(4, self.company.id)], "company_id": company2.id}
        )

        # Set company 2 settings and read them back
        #
        sequence2 = (
            self.env["ir.sequence"]
            .with_company(company2.id)
            .create({"name": "EE ID2", "code": "hr.employee.id2"})
        )
        self.assertEqual(sequence2.company_id.id, company2.id)
        vals2 = {
            "employee_id_random_digits": DIGITS2,
            "employee_id_gen_method": METHOD2,
            "employee_id_sequence": sequence2.id,
        }
        Settings.create(vals2).execute()
        res2 = Settings.default_get(fields)

        # Change back to first company and read its settings
        self.env.user.write({"company_id": company.id})
        res1 = Settings.default_get(fields)

        self.assertNotEqual(res1["employee_id_random_digits"], DIGITS2)
        self.assertNotEqual(res1["employee_id_gen_method"], METHOD2)
        self.assertNotEqual(res1["employee_id_sequence"], sequence2.id)
        self.assertEqual(res2["employee_id_random_digits"], DIGITS2)
        self.assertEqual(res2["employee_id_gen_method"], METHOD2)
        self.assertEqual(res2["employee_id_sequence"], sequence2.id)

    def test_generate_identification_id_exception(self):
        sequence = self.sequence
        company = self.company
        company.employee_id_gen_method = "sequence"
        company.employee_id_sequence = sequence.id

        # Create an user with 00001 identification_id
        self.employee_model.create(
            {"name": "First Employee", "identification_id": "00001"}
        )

        # Override the company employee_id_sequence sequence next_by_id
        # method to always return 00001
        with patch(
            "odoo.addons.base.models.ir_sequence.IrSequence.next_by_id",
            return_value="00001",
        ):
            with self.assertRaises(UserError):
                self.employee_model.create({"name": "Second Employee"})
