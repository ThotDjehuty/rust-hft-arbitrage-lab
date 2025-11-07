use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConnectorError {
    #[error("network error: {0}")]
    Network(String),

    #[error("parse error: {0}")]
    Parse(String),

    #[error("other: {0}")]
    Other(String),
}
