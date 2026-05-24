import math
from typing import NamedTuple


class ECEFCoords(NamedTuple):
    x: float
    y: float
    z: float


class ENUCoords(NamedTuple):
    e: float  # East
    n: float  # North
    u: float  # Up


class GeometryService:
    # WGS84 ellipsoid constants
    A = 6378137.0         # semi-major axis (meters)
    F = 1.0 / 298.257223563  # flattening
    B = A * (1.0 - F)      # semi-minor axis
    E2 = (A**2 - B**2) / A**2

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points on the Earth's surface
        using the Haversine formula. Returns distance in kilometers.
        """
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        earth_radius_km = 6371.0
        return earth_radius_km * c

    def wgs84_to_ecef(self, lat: float, lon: float, alt: float = 0.0) -> ECEFCoords:
        """
        Converts WGS-84 Geodetic coordinates (Lat, Lon, Alt) to ECEF (Earth-Centered Earth-Fixed) 
        Cartesian coordinates (X, Y, Z in meters).
        """
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        # Prime vertical radius of curvature
        n = self.A / math.sqrt(1.0 - self.E2 * (math.sin(lat_rad) ** 2))
        
        x = (n + alt) * math.cos(lat_rad) * math.cos(lon_rad)
        y = (n + alt) * math.cos(lat_rad) * math.sin(lon_rad)
        z = (n * (1.0 - self.E2) + alt) * math.sin(lat_rad)
        
        return ECEFCoords(x, y, z)

    def wgs84_to_enu(self, lat: float, lon: float, alt: float, 
                     ref_lat: float, ref_lon: float, ref_alt: float) -> ENUCoords:
        """
        Converts WGS-84 Geodetic coordinates to local ENU (East, North, Up) coordinates 
        relative to a local tangent plane origin point (ref_lat, ref_lon, ref_alt).
        This is perfect for Flutter 3D renderers to avoid floating point jitter on massive ECEF scales.
        """
        # Convert target and reference to ECEF
        target_ecef = self.wgs84_to_ecef(lat, lon, alt)
        ref_ecef = self.wgs84_to_ecef(ref_lat, ref_lon, ref_alt)
        
        dx = target_ecef.x - ref_ecef.x
        dy = target_ecef.y - ref_ecef.y
        dz = target_ecef.z - ref_ecef.z
        
        ref_lat_rad = math.radians(ref_lat)
        ref_lon_rad = math.radians(ref_lon)
        
        # Rotation matrix to local tangent plane
        e = -math.sin(ref_lon_rad) * dx + math.cos(ref_lon_rad) * dy
        
        n = (-math.sin(ref_lat_rad) * math.cos(ref_lon_rad) * dx - 
             math.sin(ref_lat_rad) * math.sin(ref_lon_rad) * dy + 
             math.cos(ref_lat_rad) * dz)
             
        u = (math.cos(ref_lat_rad) * math.cos(ref_lon_rad) * dx + 
             math.cos(ref_lat_rad) * math.sin(ref_lon_rad) * dy + 
             math.sin(ref_lat_rad) * dz)
             
        return ENUCoords(e, n, u)


geometry_service = GeometryService()
