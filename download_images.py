from ddgs import DDGS
import os
import requests
import time
import random

queries = {
    "pipe_crack": "water pipe crack leakage",
    "rust_corrosion": "rusted water pipeline corrosion",
    "joint_leakage": "pipe joint water leakage",
    "burst_pipe": "burst water pipe flooding"
}

base_dir = "dataset"

for folder, query in queries.items():
    save_path = os.path.join(base_dir, folder)
    os.makedirs(save_path, exist_ok=True)

    print(f"\nDownloading {folder} images...")

    with DDGS() as ddgs:
        results = ddgs.images(query, max_results=150)

        for i, result in enumerate(results):
            try:
                img_url = result["image"]

                response = requests.get(
                    img_url,
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )

                with open(f"{save_path}/{folder}_{i}.jpg", "wb") as f:
                    f.write(response.content)

                # ⭐ Anti-block delay
                time.sleep(random.uniform(1, 2))

            except:
                continue

print("\n✅ Dataset Download Complete")