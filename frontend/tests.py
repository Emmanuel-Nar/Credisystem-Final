from django.test import RequestFactory, SimpleTestCase

from credisystem.errors import bad_request, page_not_found, permission_denied, server_error


class ManejadoresErrorTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_404_html_es_amigable_y_no_expone_detalles(self):
        response = page_not_found(self.factory.get("/ruta-inexistente/"), Exception("dato sensible"))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página no encontrada", status_code=404)
        self.assertNotContains(response, "dato sensible", status_code=404)

    def test_403_api_devuelve_json_controlado(self):
        response = permission_denied(self.factory.get("/api/privado/"), Exception("secreto"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn(b"secreto", response.content)

    def test_400_api_devuelve_mensaje_generico(self):
        response = bad_request(self.factory.post("/api/datos/"), Exception("payload interno"))
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Solicitud inv", response.content)
        self.assertNotIn(b"payload interno", response.content)

    def test_500_html_no_expone_excepciones(self):
        response = server_error(self.factory.get("/fallo/"))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Error interno", status_code=500)
