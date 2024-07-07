import re
from math import log

import fire
import geoip2.database
import matplotlib.colors
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from cartopy.io.img_tiles import *
from sklearn.cluster import DBSCAN

relay_pattern = re.compile(
    '(^r (?P<nickname>\S*) (?P<id>\S*) (?P<digest>\S*) (?P<publication>\S* \S*) (?P<ip>\S*) (?P<orport>\S*) (?P<dirport>\S*)$\n)'
    '(^a (?P<ipv6>\S*)$\n)?'
    '(^s (?P<flags>(\S ?)*)$\n)'
    '(^v (?P<version>.*)$\n)'
    '(^pr .*$\n)?'
    '(?P<weight>^w (Bandwidth=(?P<bandwidth>\d*)).*$\n)'
    '(?P<ports>^p .*$)', re.MULTILINE)


def cluster_coordinates(coordinates, eps=1.5, weight=False):
    """
    Use DBSCAN to cluster points and have a readable map
    :param coordinates: list of points (lat, lon)
    :param eps: control the density of the cluster
    :param weight: if True, use consensus weight instead of number of relays
    """
    dbscan = DBSCAN(eps=eps, min_samples=1)
    lat_lon = coordinates[:, [0, 1]]
    dbscan.fit(lat_lon)
    labels = dbscan.labels_
    cluster_centers = []
    cluster_counts = []
    unique_labels = set(labels)
    for label in unique_labels:
        if label == -1:
            continue
        cluster_mask = (labels == label)
        cluster_points = coordinates[cluster_mask]
        cluster_centers.append(np.mean(cluster_points[:, [0, 1]], axis=0))
        if weight:
            cluster_counts.append(np.sum(cluster_points[:, [2]]))
        else:
            cluster_counts.append(len(cluster_points))

    r = list(zip(cluster_centers, cluster_counts))
    return r, max(cluster_counts), min(cluster_counts)


def geo_ip(ip, reader):
    """
    Geocode IP address using the given reader
    :param ip: IP address
    :param reader: a geoip2.database.Reader
    :return: [lon, lat] location
    """
    response = reader.city(ip)
    return [response.location.longitude, response.location.latitude]


def get_details_from_consensus(filename):
    """
    Get the IP addresses of the relays present in the consensus at filename
    :param filename: filename of the consensus
    :return: list of IP of the relays in the consensus
    """
    result = []
    with open(filename, 'r') as f:
        for match in relay_pattern.finditer(f.read()):
            result.append(match.groupdict())
    return result


def main(consensus_file, geoip_data_file, eps=1.5, weight=False):
    """
    Create a map based on the consensus_file and geoip_data_file
    :param consensus_file: filename of a Tor consensus, see https://metrics.torproject.org/collector/recent/relay-descriptors/consensuses/
    :param geoip_data_file: MaxMind mmdb filename, see https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
    :param eps: control the density of the cluster on the map
    :param weight: if True, use consensus weight instead of number of relays
    """
    print('Reading consensus file')
    relays = get_details_from_consensus(consensus_file)
    print(f'Found {len(relays)} relays')
    points = list()
    print('Geocoding IP addresses')
    reader = geoip2.database.Reader(geoip_data_file)
    for relay in relays:
        p = geo_ip(relay['ip'], reader)
        if p[0] is None or p[1] is None:
            print(f"Could not geocode the following IP: {relay['ip']}. Skipping it")
        else:
            points.append(p + [int(relay['bandwidth'])])
    points = np.array(points)
    points, vmax, vmin = cluster_coordinates(points, eps=eps, weight=weight)

    fig = plt.figure(figsize=(10, 5))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 0.05], figure=fig)
    ax = fig.add_subplot(gs[0], projection=ccrs.PlateCarree())

    ax.stock_img()
    ax.coastlines()

    # TODO if you want to use OSM data with Mapbox, create an account and a custom style on Mapbox.
    #  Then, fill the credentials below, comment the ax.stock_img() and ax.coastlines() lines and
    #  uncomment the lines below
    #  see https://docs.mapbox.com/help/tutorials/create-a-custom-style/
    # osm_tiles = MapboxStyleTiles(
    #     access_token='',
    #     map_id='',
    #     username='',
    #     cache=False)
    # ax.add_image(osm_tiles, 4)

    cmap = plt.cm.hot
    norm = matplotlib.colors.LogNorm(vmin=vmin, vmax=vmax)
    div = 2000 if weight else 1
    for pos, count in points:
        ax.plot(pos[0], pos[1], 'o', markersize=max(4 * log(count/div, 10), 2), transform=ccrs.PlateCarree(),
                color=cmap(norm(count)))

    ax.set_global()
    plt.box(False)
    ax.set_extent([-170, 180, -60, 85], crs=ccrs.PlateCarree())
    cb_ax = fig.add_subplot(gs[1])

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cbar = plt.colorbar(sm, cax=cb_ax, orientation='horizontal')
    if weight:
        cbar.set_label('Consensus weight')
    else:
        cbar.set_label('Number of relays')

    plt.tight_layout()
    print('Saving map as map.png')
    plt.savefig('map.png', dpi=300)


if __name__ == '__main__':
    fire.Fire(main)
