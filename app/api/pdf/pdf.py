from fastapi import APIRouter

from app.api.response import ResponseCode
from app.core.base_endpoint import BaseHTTPEndpoint
from app.services.pdf_service import PDFService
from app.core.database import dbm

router = APIRouter()


class PDFTestEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        params = request.query_params
        async with dbm.session('report_db') as db:
            pdf_service = PDFService()
            report_type = params.get("report_type", "industry")
            report_id = int(params.get("report_id", 0))


            try:
                result = await pdf_service.process_pdf(report_type=report_type, report_id=report_id)
                return self.success_response({
                    "message": "PDF processing completed",
                    "output_path": result
                })
            except Exception as e:
                return self.error_response(
                    code=ResponseCode.server_error,
                    message=f"PDF processing failed: {str(e)}"
                )

    async def post(self, request):
        return self.success_response({"message": "POST request received"})


router.add_route("/test", PDFTestEndpoint, methods=["GET", "POST"])
