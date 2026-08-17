class TUSAŞRAGException(Exception):
    pass

class DocumentProcessingError(TUSAŞRAGException):
    pass

class EmbeddingError(TUSAŞRAGException):
    pass

class RetrievalError(TUSAŞRAGException):
    pass

class LLMError(TUSAŞRAGException):
    pass

class ConfigurationError(TUSAŞRAGException):
    pass
