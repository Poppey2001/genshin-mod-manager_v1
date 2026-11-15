//! Prüft und entpackt Archive: `archive_check <archiv> [ziel]`
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let source = std::path::Path::new(&args[1]);
    match gmm_core::archive::inspect_archive(source) {
        Ok(report) => {
            println!("entries={} blocked={}", report.entry_count, report.blocked);
            for issue in &report.issues {
                println!("  {:?} {} {:?}", issue.severity, issue.code, issue.member);
            }
        }
        Err(error) => println!("inspect error: {error}"),
    }
    if let Some(target) = args.get(2) {
        match gmm_core::archive::extract_archive_securely(source, std::path::Path::new(target), None) {
            Ok(_) => println!("extracted"),
            Err(error) => println!("extract error: {}", error.to_string().lines().next().unwrap_or("")),
        }
    }
}
