'''Chain-specific Darkcoin code'''
from cryptocur import CryptoCur, hash_encode, hash_decode, rev_hex, int_to_hex, sha256
import os
import darkcoin_hash as darkhash

HashX11 = lambda x: darkhash.getPoWHash(x)

class Darkcoin(CryptoCur):
    chain_index = 5
    coin_name = 'Darkcoin'
    code = 'DRK'
    p2pkh_version = 76
    p2sh_version = 16
    wif_version = 204
    ext_pub_version = '02fe52f8'
    ext_priv_version = '02fe52cc'

    DUST_THRESHOLD = 5430
    MIN_RELAY_TX_FEE = 1000
    RECOMMENDED_FEE = 50000
    COINBASE_MATURITY = 100

    block_explorers = {
        'Blockchains': 'http://blockchains.io/drk/',
        'CryptoID': 'https://chainz.cryptoid.info/drk/',
        'CoinPlorer': 'https://coinplorer.com/DRK/',
        'Official': 'http://explorer.darkcoin.io/',
    }

    base_units = {
        'DRK': 8,
        'mDRK': 5,
        'uDRK': 2,
        'duffs': 0
    }

    chunk_size = 2016

    # Network
    DEFAULT_PORTS = {'t':'50001', 's':'50002', 'h':'8081', 'g':'8082'}

    DEFAULT_SERVERS = {
        'descartes.darkco.in':DEFAULT_PORTS,       # vertoe
        'electrum.darkcointalk.org':DEFAULT_PORTS, # propulsion
        'drk1.electrum-servers.us':DEFAULT_PORTS,  # elm4ever
        'electrum.drk.siampm.com':DEFAULT_PORTS,   # thelazier
        'electrum-drk.club':DEFAULT_PORTS,         # duffman
        'drk.khavr.com':DEFAULT_PORTS,             # akhavr
    }

    def set_headers_path(self, path):
        self.headers_path = path

    def path(self):
        return self.headers_path

    def verify_chain(self, chain):

        first_header = chain[0]
        prev_header = self.read_header(first_header.get('block_height') -1)

        for header in chain:

            height = header.get('block_height')

            prev_hash = self.hash_header(prev_header)
#            bits, target = self.get_target(height/2016, chain)
            _hash = self.hash_header(header)
            try:
                assert prev_hash == header.get('prev_block_hash')
#                assert bits == header.get('bits')
#                assert int('0x'+_hash,16) < target
            except Exception:
                return False

            prev_header = header

        return True


    def verify_chunk(self, index, hexdata):
        data = hexdata.decode('hex')
        height = index*2016
        num = len(data)/80

        if index == 0:
            previous_hash = ("0"*64)
        else:
            prev_header = self.read_header(index*2016-1)
            if prev_header is None: raise
            previous_hash = self.hash_header(prev_header)

#       bits, target = self.get_target(index)

        for i in range(num):
            height = index*2016 + i
            raw_header = data[i*80:(i+1)*80]
            header = self.header_from_string(raw_header)
            _hash = self.hash_header(header)
            assert previous_hash == header.get('prev_block_hash')
#            assert bits == header.get('bits')
#            assert int('0x'+_hash,16) < target

            previous_header = header
            previous_hash = _hash

        self.save_chunk(index, data)
#        print_error("validated chunk %d"%height)


    def header_to_string(self, res):
        s = int_to_hex(res.get('version'),4) \
            + rev_hex(res.get('prev_block_hash')) \
            + rev_hex(res.get('merkle_root')) \
            + int_to_hex(int(res.get('timestamp')),4) \
            + int_to_hex(int(res.get('bits')),4) \
            + int_to_hex(int(res.get('nonce')),4)
        return s

    def header_from_string(self, s):
        hex_to_int = lambda s: int('0x' + s[::-1].encode('hex'), 16)
        h = {}
        h['version'] = hex_to_int(s[0:4])
        h['prev_block_hash'] = hash_encode(s[4:36])
        h['merkle_root'] = hash_encode(s[36:68])
        h['timestamp'] = hex_to_int(s[68:72])
        h['bits'] = hex_to_int(s[72:76])
        h['nonce'] = hex_to_int(s[76:80])
        return h


    def hash_header(self, header):
        return rev_hex(HashX11(self.header_to_string(header).decode('hex')).encode('hex'))


    def save_chunk(self, index, chunk):
        filename = self.path()
        f = open(filename,'rb+')
        f.seek(index*2016*80)
        h = f.write(chunk)
        f.close()


    def save_header(self, header):
        data = self.header_to_string(header).decode('hex')
        assert len(data) == 80
        height = header.get('block_height')
        filename = self.path()
        f = open(filename,'rb+')
        f.seek(height*80)
        h = f.write(data)
        f.close()


    def read_header(self, block_height):
        name = self.path()
        if os.path.exists(name):
            f = open(name,'rb')
            f.seek(block_height*80)
            h = f.read(80)
            f.close()
            if len(h) == 80:
                h = self.header_from_string(h)
                return h

    def get_target(self, index, chain=None):
        if chain is None:
            chain = []  # Do not use mutables as default values!

        max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        if index == 0: return 0x1d00ffff, max_target

        first = self.read_header((index-1)*2016)
        last = self.read_header(index*2016-1)
        if last is None:
            for h in chain:
                if h.get('block_height') == index*2016-1:
                    last = h

        nActualTimespan = last.get('timestamp') - first.get('timestamp')
        nTargetTimespan = 24*60*60
        nActualTimespan = max(nActualTimespan, nTargetTimespan/4)
        nActualTimespan = min(nActualTimespan, nTargetTimespan*4)

        bits = last.get('bits')
        # convert to bignum
        MM = 256*256*256
        a = bits%MM
        if a < 0x8000:
            a *= 256
        target = (a) * pow(2, 8 * (bits/MM - 3))

        # new target
        new_target = min( max_target, (target * nActualTimespan)/nTargetTimespan )

        # convert it to bits
        c = ("%064X"%new_target)[2:]
        i = 31
        while c[0:2]=="00":
            c = c[2:]
            i -= 1

        c = int('0x'+c[0:6],16)
        if c >= 0x800000:
            c /= 256
            i += 1

        new_bits = c + MM * i
        return new_bits, new_target

