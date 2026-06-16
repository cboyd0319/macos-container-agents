use std::io::{Cursor, Read, Write};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, Shutdown, TcpListener, TcpStream};
use std::thread;
use std::time::Duration;

use super::*;

#[test]
fn policy_allows_exact_and_subdomain_hosts_only() {
    let policy = EgressPolicy::new(&["api.example.com".to_string()]).expect("policy");

    assert!(policy.allows("api.example.com", 443));
    assert!(policy.allows("chat.api.example.com", 443));
    assert!(!policy.allows("example.com", 443));
    assert!(!policy.allows("api.example.com", 80));
    assert!(!policy.allows("127.0.0.1", 443));
}

#[test]
fn upstream_address_safety_rejects_private_and_documentation_ranges() {
    assert!(!is_safe_upstream_address(IpAddr::V4(Ipv4Addr::new(
        10, 0, 0, 1
    ))));
    assert!(!is_safe_upstream_address(IpAddr::V4(Ipv4Addr::new(
        192, 168, 1, 1
    ))));
    assert!(!is_safe_upstream_address(IpAddr::V4(Ipv4Addr::new(
        203, 0, 113, 10
    ))));
    assert!(!is_safe_upstream_address(IpAddr::V6(Ipv6Addr::LOCALHOST)));
    assert!(is_safe_upstream_address(IpAddr::V4(Ipv4Addr::new(
        93, 184, 216, 34
    ))));
}

#[test]
fn parse_connect_target_normalizes_ipv6_brackets() {
    assert_eq!(
        parse_connect_target("[2001:db8::1]:443").expect("target"),
        ("2001:db8::1".to_string(), 443)
    );
}

#[test]
fn proxy_request_reader_does_not_consume_tunneled_bytes() {
    let mut request = Cursor::new(
        b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\nTLS_CLIENT_HELLO",
    );

    assert_eq!(
        read_proxy_request_line(&mut request).expect("request line"),
        Some("CONNECT example.com:443 HTTP/1.1".to_string())
    );

    let mut remaining = Vec::new();
    request
        .read_to_end(&mut remaining)
        .expect("remaining bytes");
    assert_eq!(remaining, b"TLS_CLIENT_HELLO");
}

#[test]
fn relay_moves_bytes_in_both_directions() {
    let upstream_listener = TcpListener::bind(("127.0.0.1", 0)).expect("upstream listener");
    let upstream_address = upstream_listener.local_addr().expect("upstream address");
    let upstream_server = thread::spawn(move || {
        let (mut stream, _) = upstream_listener.accept().expect("upstream accept");
        let mut request = [0u8; 4];
        stream.read_exact(&mut request).expect("upstream read");
        assert_eq!(&request, b"ping");
        stream.write_all(b"pong").expect("upstream write");
        stream.shutdown(Shutdown::Write).expect("upstream shutdown");
    });

    let client_listener = TcpListener::bind(("127.0.0.1", 0)).expect("client listener");
    let client_address = client_listener.local_addr().expect("client address");
    let relay_thread = thread::spawn(move || {
        let (proxy_client, _) = client_listener.accept().expect("proxy accept");
        let upstream = TcpStream::connect(upstream_address).expect("upstream connect");
        proxy_client
            .set_nonblocking(true)
            .expect("proxy nonblocking");
        upstream
            .set_nonblocking(true)
            .expect("upstream nonblocking");
        relay(proxy_client, upstream, Duration::from_secs(2));
    });
    let mut client = TcpStream::connect(client_address).expect("client connect");

    client.write_all(b"ping").expect("client write");
    client.shutdown(Shutdown::Write).expect("client shutdown");
    let mut response = Vec::new();
    client.read_to_end(&mut response).expect("client read");
    assert_eq!(response, b"pong");
    relay_thread.join().expect("relay");
    upstream_server.join().expect("upstream server");
}
