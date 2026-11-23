import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import httpx

async def run_single_job(
    client: httpx.AsyncClient,
    base_url: str,
    input_file: Path,
    output_dir: Path,
    timeout_sec: int = 180
) -> Dict[str, Any]:
    print(f"\n[Batch Runner] Processing: {input_file.name}")
    start_time = time.time()
    
    try:
        content = json.loads(input_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Invalid JSON in {input_file.name}: {e}")
        return {"file": input_file.name, "status": "failed", "error": str(e)}

    # Submit job
    submit_url = f"{base_url.rstrip('/')}/api/v1/broll/jobs"
    headers = {"Idempotency-Key": f"batch_{input_file.stem}_{int(time.time())}"}
    
    try:
        res = await client.post(submit_url, json=content, headers=headers, timeout=20.0)
        if res.status_code not in [200, 202]:
            err_msg = f"HTTP {res.status_code}: {res.text}"
            print(f"  [ERROR] Submit failed: {err_msg}")
            return {"file": input_file.name, "status": "failed", "error": err_msg}

        job_info = res.json()
        job_id = job_info.get("job_id")
        print(f"  Job submitted: {job_id} (Status: {job_info.get('status')})")
    except Exception as e:
        print(f"  [ERROR] Network error during submission: {e}")
        return {"file": input_file.name, "status": "failed", "error": str(e)}

    # Poll status until finished or timeout
    poll_url = f"{base_url.rstrip('/')}/api/v1/jobs/{job_id}"
    elapsed = 0
    poll_interval = 2.0

    while elapsed < timeout_sec:
        await asyncio.sleep(poll_interval)
        elapsed = time.time() - start_time
        
        try:
            status_res = await client.get(poll_url, timeout=10.0)
            if status_res.status_code == 200:
                data = status_res.json()
                st = data.get("status")
                prog = data.get("progress", 0)
                stage = data.get("stage", "")
                print(f"  [{job_id}] Progress: {prog}% ({stage})", end="\r")

                if st == "succeeded":
                    print(f"\n  [SUCCESS] Job {job_id} completed in {elapsed:.2f}s")
                    # Download outputs into output_dir / input_file.stem
                    job_out_dir = output_dir / input_file.stem
                    job_out_dir.mkdir(parents=True, exist_ok=True)
                    
                    result = data.get("result", {})
                    # Download videos
                    for ratio, v_url in result.get("videos", {}).items():
                        ratio_clean = ratio.replace(":", "-")
                        v_res = await client.get(v_url, timeout=60.0)
                        (job_out_dir / f"video_{ratio_clean}.mp4").write_bytes(v_res.content)

                    # Download captions.srt
                    if result.get("captions"):
                        c_res = await client.get(result["captions"], timeout=10.0)
                        (job_out_dir / "captions.srt").write_bytes(c_res.content)

                    # Download timeline.json
                    if result.get("timeline"):
                        t_res = await client.get(result["timeline"], timeout=10.0)
                        (job_out_dir / "timeline.json").write_bytes(t_res.content)

                    # Download manifest.json
                    if result.get("manifest"):
                        m_res = await client.get(result["manifest"], timeout=10.0)
                        (job_out_dir / "manifest.json").write_bytes(m_res.content)

                    return {
                        "file": input_file.name,
                        "job_id": job_id,
                        "status": "succeeded",
                        "duration_seconds": round(elapsed, 2),
                        "output_dir": str(job_out_dir)
                    }

                elif st == "failed":
                    err_info = data.get("error", {})
                    print(f"\n  [FAILED] Job {job_id}: {err_info.get('message')}")
                    return {
                        "file": input_file.name,
                        "job_id": job_id,
                        "status": "failed",
                        "error": err_info
                    }
        except Exception as e:
            logger.debug(f"Polling warning: {e}")

    print(f"\n  [TIMEOUT] Job {job_id} timed out after {timeout_sec}s")
    return {"file": input_file.name, "job_id": job_id, "status": "timeout"}

async def main_async(args):
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files: List[Path] = []
    if input_path.is_file():
        input_files.append(input_path)
    elif input_path.is_dir():
        input_files = sorted(list(input_path.glob("*.json")))
    else:
        print(f"Error: Input path '{input_path}' not found.")
        sys.exit(1)

    if not input_files:
        print(f"No JSON input files found in '{input_path}'.")
        sys.exit(1)

    print(f"Starting batch runner on {len(input_files)} input files...")
    print(f"API Target: {args.api_url}")
    print(f"Output Directory: {output_dir.resolve()}")

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for f in input_files:
            res = await run_single_job(client, args.api_url, f, output_dir, args.timeout)
            results.append(res)

    summary_file = output_dir / "batch_summary.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n==========================================")
    print(f"Batch execution completed!")
    print(f"Summary written to: {summary_file}")
    print(f"==========================================")

def main():
    parser = argparse.ArgumentParser(description="IncuBrix B-Roll Engine Batch Runner (Integration Standard #10)")
    parser.add_argument("--input", "-i", required=True, help="Path to a JSON input file or directory of JSON input files")
    parser.add_argument("--output", "-o", required=True, help="Directory to save downloaded results and videos")
    parser.add_argument("--api-url", "-u", default="http://localhost:8000", help="Base URL of running IncuBrix API service")
    parser.add_argument("--timeout", "-t", type=int, default=180, help="Per-job timeout in seconds")

    args = parser.parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
