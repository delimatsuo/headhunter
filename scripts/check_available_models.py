
import vertexai
from vertexai.generative_models import GenerativeModel

def list_models():
    project_id = "headhunter-ai-0088"
    location = "us-central1"
    
    try:
        vertexai.init(project=project_id, location=location)
        print(f"Initialized Vertex AI for {project_id} in {location}")
        
        # Try to list models if possible, or just try to instantiate a few common ones
        models_to_try = [
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash",
            "gemini-1.0-pro-001",
            "gemini-1.0-pro",
            "gemini-pro",
            "gemini-1.5-pro-001",
            "gemini-1.5-pro-preview-0409",
            "gemini-1.5-pro"
        ]
        
        print("\nTesting model availability:")
        for model_name in models_to_try:
            try:
                model = GenerativeModel(model_name)
                # Just try to generate something simple
                response = model.generate_content("Hello")
                print(f"✅ {model_name}: Available (Response: {response.text.strip()})")
            except Exception as e:
                print(f"❌ {model_name}: Failed ({e})")
                
    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    list_models()