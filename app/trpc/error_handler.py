from fastapi import HTTPException

class TrpcErrorHandler:
    @staticmethod
    def handle(error) -> dict:
        return {"error": str(error)}
