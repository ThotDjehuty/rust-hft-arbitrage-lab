use signature_optimal_stopping::*;
use std::fs::File;
use std::io::Read;
use serde_json::Value;
use std::env;
use std::fs::write;

fn print_usage() {
    eprintln!("Usage: trainer train --input <input.json> --output <out.json>");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_usage();
        return Ok(());
    }
    if args[1] != "train" {
        print_usage();
        return Ok(());
    }

    let mut inpath = "";
    let mut outpath = "weights.json";
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--input" => {
                if i + 1 < args.len() { inpath = &args[i+1]; i += 2; continue; }
                else { print_usage(); return Ok(()); }
            }
            "--output" => {
                if i + 1 < args.len() { outpath = &args[i+1]; i += 2; continue; }
                else { print_usage(); return Ok(()); }
            }
            _ => { i += 1; }
        }
    }

    if inpath.is_empty() {
        eprintln!("Input path is required");
        print_usage();
        return Ok(());
    }

    let mut input = String::new();
    let mut f = File::open(inpath)?;
    f.read_to_string(&mut input)?;
    let v: Value = serde_json::from_str(&input)?;
    let params = &v["params"];
    let trunc = params["truncation"].as_u64().unwrap_or(2) as usize;
    let ridge = params["ridge"].as_f64().unwrap_or(1e-3);
    let samples_v = v["samples"].as_array().ok_or("samples must be array")?;

    // convert to TrainingSample
    let mut samples: Vec<signature_optimal_stopping::TrainingSample> = Vec::new();
    for s in samples_v {
        let traj_v = s["traj"].as_array().ok_or("traj must be array")?;
        let mut traj: signature_optimal_stopping::Trajectory = Vec::new();
        for point in traj_v {
            let pt = point.as_array().ok_or("point must be array")?;
            let row: Vec<f64> = pt.iter().map(|x| x.as_f64().unwrap()).collect();
            traj.push(row);
        }
        let reward = s["reward"].as_f64().unwrap_or(0.0);
        samples.push(signature_optimal_stopping::TrainingSample { traj, reward });
    }

    let d = samples[0].traj[0].len();
    let dim = signature_optimal_stopping::compute_feature_dim(d, trunc);
    let mut stopper = signature_optimal_stopping::SignatureStopper::new(signature_optimal_stopping::SigParams { truncation: trunc, ridge }, dim);
    stopper.train(&samples)?;

    // write weights as json
    let weights = stopper.weights.ok_or("missing weights")?;
    let w_vec: Vec<f64> = weights.to_vec();
    let out = serde_json::json!({ "weights": w_vec, "params": { "truncation": trunc, "ridge": ridge }});
    write(outpath, serde_json::to_string(&out)?)?;
    println!("Written weights to {}", outpath);
    Ok(())
}
