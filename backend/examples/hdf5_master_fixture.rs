#[path = "../tests/common/hdf5_master_fixtures.rs"]
mod fixtures;
fn main() {
    let directory = std::path::PathBuf::from(std::env::args().nth(1).expect("output directory"));
    fixtures::generate(&directory);
    fixtures::compressed(
        &directory.join("virtual.h5"),
        &directory.join("virtual.h5.gz"),
    );
}
