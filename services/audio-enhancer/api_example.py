"""
Примеры использования Audio Enhancer API
"""

import requests


def enhance_audio_example():
    """Пример полной обработки аудио"""
    url = "http://localhost:7860/enhance"

    with open("audio.mp3", "rb") as f:
        files = {"file": f}
        data = {
            "noise_reduction": True,
            "normalize_volume": True,
            "enhance_speech": True,
            "remove_silence": True,
            "target_sample_rate": 16000,
        }

        response = requests.post(url, files=files, data=data)

    if response.status_code == 200:
        with open("enhanced.wav", "wb") as f:
            f.write(response.content)
        print("✅ Аудио успешно обработано: enhanced.wav")
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)


def denoise_only_example():
    """Пример быстрого шумоподавления"""
    url = "http://localhost:7860/denoise"

    with open("noisy_audio.mp3", "rb") as f:
        files = {"file": f}
        data = {
            "stationary": True,
            "prop_decrease": 0.8,
        }

        response = requests.post(url, files=files, data=data)

    if response.status_code == 200:
        with open("denoised.wav", "wb") as f:
            f.write(response.content)
        print("✅ Шумоподавление завершено: denoised.wav")
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)


def health_check_example():
    """Проверка работоспособности сервиса"""
    url = "http://localhost:7860/health"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Сервис работает")
        print(f"   Статус: {data['status']}")
        print(f"   Silero VAD: {data['silero_vad_loaded']}")
    else:
        print(f"❌ Сервис недоступен: {response.status_code}")


if __name__ == "__main__":
    print("=== Audio Enhancer API Examples ===\n")

    print("1. Проверка работоспособности")
    health_check_example()
    print()

    print("2. Полная обработка аудио")
    # enhance_audio_example()
    print("   (раскомментируйте для запуска)")
    print()

    print("3. Быстрое шумоподавление")
    # denoise_only_example()
    print("   (раскомментируйте для запуска)")
