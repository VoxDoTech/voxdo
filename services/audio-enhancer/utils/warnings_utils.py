"""Управление предупреждениями от сторонних библиотек."""

import warnings


def setup_warnings_filters():
    """Настраивает фильтры для подавления известных предупреждений."""
    
    # DeepFilterNet предупреждения
    warnings.filterwarnings(
        "ignore",
        message=r".*torch\.load.*weights_only=False.*",
        category=FutureWarning,
        module=r"df\.checkpoint",
    )
    
    # Torchaudio AudioMetaData предупреждения
    warnings.filterwarnings(
        "ignore",
        message=r".*torchaudio\.backend\.common\.AudioMetaData.*has been moved.*",
        category=UserWarning,
        module=r"df\.io",
    )
    
    # Все AudioMetaData предупреждения
    warnings.filterwarnings(
        "ignore",
        message=r".*AudioMetaData.*has been moved.*",
        category=UserWarning,
    )
    
    # Torchaudio set_audio_backend предупреждения
    warnings.filterwarnings(
        "ignore",
        message=r".*torchaudio\._backend\.set_audio_backend has been deprecated.*",
        category=UserWarning,
    )
    
    # Pyannote предупреждения
    warnings.filterwarnings(
        "ignore",
        message=r".*pyannote.*",
        category=UserWarning,
    )


# Вызываем при импорте
setup_warnings_filters()
