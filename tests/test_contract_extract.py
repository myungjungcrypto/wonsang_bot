import unittest

from wonsang_bot.detector.contract_extract import (
    extract_contracts_from_text,
    normalize_chain,
)

A40 = "a" * 40
B40 = "b" * 40
C40 = "c" * 40
D40 = "d" * 40
# 실제 wrapped SOL 민트 주소(유효 base58, 44자)
SOL = "So11111111111111111111111111111111111111112"
TRON = "T" + "J" * 33  # 34자, base58 형태


class TestExtract(unittest.TestCase):
    def test_evm_with_korean_hint(self):
        cs = extract_contracts_from_text(f"네트워크: 이더리움(ERC-20)\n컨트랙트: 0x{A40}")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].chain, "ethereum")
        self.assertEqual(cs[0].address.lower(), "0x" + A40)
        self.assertEqual(cs[0].via, "announcement_body")

    def test_bep20_hint(self):
        cs = extract_contracts_from_text(f"BEP-20 컨트랙트 0x{B40}")
        self.assertEqual(cs[0].chain, "bsc")

    def test_evm_without_hint_defaults_evm(self):
        cs = extract_contracts_from_text(f"컨트랙트 주소: 0x{C40}")
        self.assertEqual(cs[0].chain, "evm")

    def test_tron(self):
        cs = extract_contracts_from_text(f"트론(TRC-20) 주소 {TRON}")
        self.assertTrue(any(c.chain == "tron" for c in cs))

    def test_solana_requires_hint(self):
        with_hint = extract_contracts_from_text(f"솔라나(SPL) 토큰 주소: {SOL}")
        self.assertTrue(any(c.chain == "solana" for c in with_hint))
        # 힌트 없으면 base58 오탐 방지를 위해 추출하지 않음
        without = extract_contracts_from_text(f"토큰 주소: {SOL}")
        self.assertFalse(any(c.chain == "solana" for c in without))

    def test_dedupe_same_address(self):
        cs = extract_contracts_from_text(f"이더리움 0x{D40} ... 다시 0x{D40}")
        self.assertEqual(len(cs), 1)

    def test_nearest_hint_pairs_addresses(self):
        text = f"이더리움 0x{A40} / 폴리곤 0x{B40}"
        cs = extract_contracts_from_text(text)
        by_addr = {c.address.lower(): c.chain for c in cs}
        self.assertEqual(by_addr["0x" + A40], "ethereum")
        self.assertEqual(by_addr["0x" + B40], "polygon")

    def test_empty(self):
        self.assertEqual(extract_contracts_from_text(""), [])
        self.assertEqual(extract_contracts_from_text(None), [])


class TestNormalizeChain(unittest.TestCase):
    def test_known(self):
        self.assertEqual(normalize_chain("이더리움"), "ethereum")
        self.assertEqual(normalize_chain("Solana"), "solana")
        self.assertEqual(normalize_chain("BEP-20"), "bsc")

    def test_unknown(self):
        self.assertIsNone(normalize_chain("듣보체인"))
        self.assertIsNone(normalize_chain(None))


if __name__ == "__main__":
    unittest.main()
