import base64
import oci

def get_oci_client():  # pragma: no cover
    config = oci.config.from_file()
    return oci.ai_document.AIServiceDocumentClient(config)

def build_request(pdf_bytes: bytes):
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    document = oci.ai_document.models.InlineDocumentDetails(data=encoded_pdf)

    return oci.ai_document.models.AnalyzeDocumentDetails(
        document=document,
        features=[
            oci.ai_document.models.DocumentFeature(feature_type="KEY_VALUE_EXTRACTION"),
            oci.ai_document.models.DocumentClassificationFeature(max_results=5),
        ],
    )
