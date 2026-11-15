class AwsComprehendSentimentAnalyzer:
    def __init__(self, region_name: str) -> None:
        self._region_name = region_name

    def analyze(self, text: str) -> tuple[str, dict[str, float]]:
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as error:
            raise RuntimeError(
                "boto3 não está instalado. Instale as dependências com: "
                ".venv/bin/pip install -r requirements.txt"
            ) from error

        comprehend = boto3.client("comprehend", region_name=self._region_name)
        try:
            response = comprehend.detect_sentiment(Text=text, LanguageCode="pt")
        except (BotoCoreError, ClientError) as error:
            raise RuntimeError(f"Falha ao analisar sentimento com AWS Comprehend: {error}") from error
        return response["Sentiment"], {
            label: float(score) for label, score in response["SentimentScore"].items()
        }
