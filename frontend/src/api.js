export async function uploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    
    // Fetch from FastAPI
    const res = await fetch("http://localhost:8000/process-depth", {
      method: "POST",
      body: formData,
    });
  
    if (!res.ok) throw new Error("Upload failed");
  
    return await res.json();  // expected: { original, layers: [...] }
  }
  